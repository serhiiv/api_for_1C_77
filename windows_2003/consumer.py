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

import pika

from config import get_settings


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
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=settings.rabbitmq_host,
                    port=settings.rabbitmq_port,
                    credentials=credentials
                )
            )
            return connection
        except Exception as exc:
            last_exception = exc
            print('[consumer] Connection attempt {0}/{1} failed, retrying in {2}s...'.format(
                attempt + 1, retries, delay))
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
        print('[consumer] received: {0}'.format(payload))
        
        settings = get_settings()
        
        # Create temporary input JSON file in win-1251 encoding
        fd_input, temp_input_file = tempfile.mkstemp(suffix='.json', dir=settings.temp_dir)
        payload_json = json.dumps(payload, ensure_ascii=False)
        payload_bytes = payload_json.encode('cp1251')
        os.write(fd_input, payload_bytes)
        os.close(fd_input)
        print('[consumer] temp input file created: {0}'.format(temp_input_file))
        
        # Call VBScript bridge
        try:
            cmd = [
                'cscript.exe',
                settings.bridge_vbs,
                temp_input_file,
                settings.path_1c,
                settings.user_1c,
                settings.pass_1c
            ]
            print('[consumer] executing: {0}'.format(' '.join(cmd)))
            
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            
            if proc.returncode != 0:
                error_msg = stderr.decode('cp1251', errors='ignore') if stderr else 'Unknown error'
                print('[consumer] VBScript error: {0}'.format(error_msg))
                response = {'status': 'error', 'detail': 'VBScript failed', 'error': error_msg}
            else:
                # Parse VBScript output to get result file path
                temp_output_file = stdout.decode('cp1251', errors='ignore').strip()
                print('[consumer] result file: {0}'.format(temp_output_file))
                
                # Read result file in win-1251 and convert to UTF-8
                if temp_output_file and os.path.exists(temp_output_file):
                    with open(temp_output_file, 'rb') as f:
                        result_bytes = f.read()
                    result_json = result_bytes.decode('cp1251')
                    result_data = json.loads(result_json)
                    print('[consumer] result: {0}'.format(result_data))
                    response = result_data
                else:
                    response = {'status': 'error', 'detail': 'Result file not found'}
                    
        except Exception as vbs_exc:
            print('[consumer] VBScript execution error: {0}'.format(vbs_exc))
            response = {'status': 'error', 'detail': 'VBScript execution failed', 'error': str(vbs_exc)}
        
        # If response is still None, create error response
        if response is None:
            response = {'status': 'error', 'detail': 'No response from VBScript'}
        
        # Send response
        reply_to = properties.reply_to
        if reply_to:
            response_json = json.dumps(response, ensure_ascii=False)
            response_body = response_json.encode('utf-8')
            ch.basic_publish(
                exchange='',
                routing_key=reply_to,
                body=response_body,
                properties=pika.BasicProperties(
                    correlation_id=properties.correlation_id
                )
            )
            print('[consumer] response sent to {0}'.format(reply_to))
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except Exception as exc:
        print('[consumer] Error processing message: {0}'.format(exc))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    finally:
        # Clean up temporary files
        try:
            if temp_input_file and os.path.exists(temp_input_file):
                os.remove(temp_input_file)
                print('[consumer] cleaned up input file: {0}'.format(temp_input_file))
        except Exception as e:
            print('[consumer] Error cleaning up input file: {0}'.format(e))
        
        try:
            if temp_output_file and os.path.exists(temp_output_file):
                os.remove(temp_output_file)
                print('[consumer] cleaned up output file: {0}'.format(temp_output_file))
        except Exception as e:
            print('[consumer] Error cleaning up output file: {0}'.format(e))


def run_consumer():
    """Run the message consumer."""
    settings = get_settings()
    connection = connect_with_retry()
    channel = connection.channel()

    # Declare input queue
    channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)
    
    # Set prefetch to 1: process one message at a time
    channel.basic_qos(prefetch_count=1)

    # Set callback for messages
    channel.basic_consume(handle_message, queue=settings.rabbitmq_queue)

    print('[consumer] listening queue: {0}'.format(settings.rabbitmq_queue))
    print('[consumer] waiting for messages...')
    
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print('[consumer] shutting down...')
        channel.stop_consuming()
        connection.close()


if __name__ == '__main__':
    run_consumer()
