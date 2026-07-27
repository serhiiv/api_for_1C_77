#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Worker for Windows Server 2003 with Python 3.4.4
Synchronous RabbitMQ consumer using pika (not aio-pika)
"""

import json
import time
import os
import tempfile
import subprocess
import logging
from logging.handlers import TimedRotatingFileHandler

import pika

from config import get_settings


LOGGER = logging.getLogger('consumer')


def get_cscript_executable(settings):
    """Pick 32-bit cscript on x64 Windows for compatibility with 1C 7.7 COM."""
    if settings.cscript_exe:
        return settings.cscript_exe

    system_root = os.environ.get('SystemRoot') or 'C:\\Windows'
    wow64_candidates = [
        os.path.join(system_root, 'SysWOW64', 'cscript.exe'),
        'C:\\Windows\\SysWOW64\\cscript.exe'
    ]
    for wow64_cscript in wow64_candidates:
        if os.path.exists(wow64_cscript):
            return wow64_cscript

    system32_cscript = os.path.join(system_root, 'System32', 'cscript.exe')
    if os.path.exists(system32_cscript):
        return system32_cscript

    return 'cscript.exe'


def setup_logging():
    """Configure logging to file with daily rotation and 5-day retention."""
    settings = get_settings()

    if not os.path.exists(settings.log_dir):
        os.makedirs(settings.log_dir)

    log_path = os.path.join(settings.log_dir, settings.log_file)
    handler = TimedRotatingFileHandler(
        log_path,
        when='midnight',
        interval=1,
        backupCount=max(settings.log_retention_days - 1, 0),
        encoding='utf-8'
    )
    handler.suffix = '%Y-%m-%d'

    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        '%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    LOGGER.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    LOGGER.addHandler(handler)
    LOGGER.propagate = False


def connect_with_retry(retries=10, delay=3):
    """Connect to RabbitMQ with retries."""
    settings = get_settings()
    last_exception = None

    for attempt in range(retries):
        try:
            credentials = pika.PlainCredentials(
                settings.rabbitmq_default_user,
                settings.rabbitmq_default_pass
            )
            params = {
                'host': settings.rabbitmq_host,
                'port': settings.rabbitmq_port,
                'credentials': credentials
            }
            
            # Pika 1.x uses 'heartbeat', Pika 0.x (e.g. 0.11.2) uses 'heartbeat_interval'
            try:
                conn_params = pika.ConnectionParameters(heartbeat=settings.rabbitmq_heartbeat, **params)
            except TypeError:
                conn_params = pika.ConnectionParameters(heartbeat_interval=settings.rabbitmq_heartbeat, **params)

            connection = pika.BlockingConnection(conn_params)
            return connection
        except Exception as exc:
            last_exception = exc
            LOGGER.warning(
                'Connection attempt %s/%s failed (%s: %s), retrying in %ss...',
                attempt + 1,
                retries,
                exc.__class__.__name__,
                exc,
                delay
            )
            time.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError('Failed to connect to RabbitMQ')


def build_result_queue_name(request_id):
    """Build output queue name for a request."""
    settings = get_settings()
    return '{0}.{1}'.format(settings.rabbitmq_result_queue_prefix, request_id)


def handle_message(ch, method, properties, body):
    """Handle incoming message from input queue and process via VBScript bridge."""
    response = None
    temp_input_file = None
    temp_output_file = None
    
    try:
        # Parse incoming message
        payload = json.loads(body.decode('utf-8'))
        LOGGER.info('received : %s', payload)
        
        settings = get_settings()
        
        # Create temporary input JSON file in win-1251 encoding
        fd_input, temp_input_file = tempfile.mkstemp(suffix='.json', dir=settings.temp_dir)
        payload_json = json.dumps(payload, ensure_ascii=False)
        payload_bytes = payload_json.encode('cp1251')
        os.write(fd_input, payload_bytes)
        os.close(fd_input)
        LOGGER.debug('temp input file created: %s', temp_input_file)
        
        # Call VBScript bridge
        try:
            cscript_exe = get_cscript_executable(settings)
            cmd = [
                cscript_exe,
                '//nologo',
                settings.bridge_vbs,
                temp_input_file,
                settings.path_1c,
                settings.user_1c,
                settings.pass_1c
            ]
            LOGGER.info('executing: %s', ' '.join(cmd))
            
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Periodically poll process and service RabbitMQ connection events (heartbeats)
            stdout, stderr = None, None
            while proc.poll() is None:
                try:
                    stdout, stderr = proc.communicate(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    try:
                        if ch.connection and ch.connection.is_open:
                            ch.connection.process_data_events(time_limit=0)
                    except Exception as evt_exc:
                        LOGGER.warning('Heartbeat/connection event error during VBScript execution: %s', evt_exc)
            
            if stdout is None:
                stdout, stderr = proc.communicate()
            
            if proc.returncode != 0:
                # cscript.exe routes WScript.Echo to stdout; stderr may contain runtime errors
                stdout_msg = stdout.decode('cp866', errors='ignore').strip() if stdout else ''
                stderr_msg = stderr.decode('cp866', errors='ignore').strip() if stderr else ''
                error_msg = stdout_msg or stderr_msg or 'Unknown error'
                LOGGER.error('VBScript error: %s', error_msg)
                response = {'status': 'error', 'detail': 'VBScript failed', 'error': error_msg}
            else:
                # Parse VBScript output to get result file path
                temp_output_file = stdout.decode('cp1251', errors='ignore').strip()
                LOGGER.debug('result file: %s', temp_output_file)
                
                # Read result file in win-1251 and convert to UTF-8
                if temp_output_file and os.path.exists(temp_output_file):
                    with open(temp_output_file, 'rb') as f:
                        result_bytes = f.read()
                    result_json = result_bytes.decode('cp1251')
                    result_data = json.loads(result_json)
                    result_preview = ' '.join(result_json[:300].split())
                    LOGGER.info('result: %s', result_preview)  # Log first 300 chars in one line
                    response = result_data
                else:
                    response = {'status': 'error', 'detail': 'Result file not found'}
                    
        except Exception as vbs_exc:
            LOGGER.exception('VBScript execution error: %s', vbs_exc)
            response = {'status': 'error', 'detail': 'VBScript execution failed', 'error': str(vbs_exc)}
        
        # If response is still None, create error response
        if response is None:
            response = {'status': 'error', 'detail': 'No response from VBScript'}
        
        # Send response
        reply_to = properties.reply_to
        if reply_to:
            response_json = json.dumps(response, ensure_ascii=False)
            response_body = response_json.encode('utf-8')
            published = False
            
            if ch.is_open and ch.connection and ch.connection.is_open:
                try:
                    ch.basic_publish(
                        exchange='',
                        routing_key=reply_to,
                        body=response_body,
                        properties=pika.BasicProperties(
                            correlation_id=properties.correlation_id
                        )
                    )
                    LOGGER.info('response sent to %s', reply_to)
                    published = True
                except Exception as pub_exc:
                    LOGGER.warning('Failed to publish response on current channel: %s', pub_exc)
            
            # Fallback: if main connection lost during execution, create temporary connection to deliver response
            if not published:
                LOGGER.warning('Main connection unusable. Trying fallback connection to send response to %s...', reply_to)
                try:
                    fallback_conn = connect_with_retry(retries=3, delay=1)
                    fallback_ch = fallback_conn.channel()
                    fallback_ch.basic_publish(
                        exchange='',
                        routing_key=reply_to,
                        body=response_body,
                        properties=pika.BasicProperties(
                            correlation_id=properties.correlation_id
                        )
                    )
                    fallback_conn.close()
                    LOGGER.info('response successfully sent to %s via fallback connection', reply_to)
                except Exception as fb_exc:
                    LOGGER.error('Failed to send response via fallback connection: %s', fb_exc)
        
        if ch.is_open:
            try:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as ack_err:
                LOGGER.warning('Failed to ack message: %s', ack_err)
        
    except Exception as exc:
        LOGGER.exception('Error processing message: %s', exc)
        if ch.is_open:
            try:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            except Exception as nack_err:
                LOGGER.warning('Failed to nack message: %s', nack_err)
    
    finally:
        # Clean up temporary files
        try:
            if temp_input_file and os.path.exists(temp_input_file):
                os.remove(temp_input_file)
                LOGGER.debug('cleaned up input file: %s', temp_input_file)
        except Exception as e:
            LOGGER.debug('Error cleaning up input file: %s', e)
        
        try:
            if temp_output_file and os.path.exists(temp_output_file):
                os.remove(temp_output_file)
                LOGGER.debug('cleaned up output file: %s', temp_output_file)
        except Exception as e:
            LOGGER.debug('Error cleaning up output file: %s', e)


def run_consumer():
    """Run the message consumer with automatic reconnection."""
    settings = get_settings()
    
    while True:
        try:
            connection = connect_with_retry()
            channel = connection.channel()

            # Declare input queue
            channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)
            
            # Set prefetch to 1: process one message at a time
            channel.basic_qos(prefetch_count=1)

            # Set callback for messages
            channel.basic_consume(handle_message, queue=settings.rabbitmq_queue)

            LOGGER.info('listening queue: %s', settings.rabbitmq_queue)
            LOGGER.info('waiting for messages...')
            
            channel.start_consuming()
        except KeyboardInterrupt:
            LOGGER.info('shutting down...')
            try:
                if 'channel' in locals() and channel.is_open:
                    channel.stop_consuming()
                if 'connection' in locals() and connection.is_open:
                    connection.close()
            except Exception:
                pass
            break
        except Exception as exc:
            LOGGER.error(
                'Consumer connection lost or error occurred (%s: %s). Reconnecting in 5 seconds...',
                exc.__class__.__name__,
                exc
            )
            time.sleep(5)


if __name__ == '__main__':
    setup_logging()
    run_consumer()
