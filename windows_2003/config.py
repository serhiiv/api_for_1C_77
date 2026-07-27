import os
from urllib.parse import quote


def _load_dotenv_if_exists():
    """Load KEY=VALUE pairs from .env near this file into process env."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv_if_exists()


class Settings(object):
    def __init__(self):
        self.app_name = os.getenv('APP_NAME', 'api_for_1C_77')
        self.rabbitmq_default_user = os.getenv('RABBITMQ_DEFAULT_USER', 'guest')
        self.rabbitmq_default_pass = os.getenv('RABBITMQ_DEFAULT_PASS', 'guest')
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
        self.rabbitmq_queue = os.getenv('RABBITMQ_QUEUE', 'events')
        self.rabbitmq_result_queue_prefix = os.getenv('RABBITMQ_RESULT_QUEUE_PREFIX', 'results')
        self.rabbitmq_result_ttl_ms = int(os.getenv('RABBITMQ_RESULT_TTL_MS', '3600000'))
        self.rabbitmq_result_queue_expires_ms = int(os.getenv('RABBITMQ_RESULT_QUEUE_EXPIRES_MS', '86400000'))
        self.rabbitmq_heartbeat = int(os.getenv('RABBITMQ_HEARTBEAT', '60'))
        
        # 1C settings
        self.path_1c = os.getenv('PATH_1C', 'C:\\Program Files\\1cv7')
        self.user_1c = os.getenv('USER_1C', '')
        self.pass_1c = os.getenv('PASS_1C', '')
        self.bridge_vbs = os.getenv('BRIDGE_VBS', os.path.dirname(__file__) + '\\bridge.vbs')
        self.cscript_exe = os.getenv('CSCRIPT_EXE', '')
        self.temp_dir = os.getenv('TEMP_DIR', os.path.expanduser('~\\AppData\\Local\\Temp'))
        self.log_dir = os.getenv('LOG_DIR', os.path.dirname(__file__) + '\\logs')
        self.log_file = os.getenv('LOG_FILE', 'consumer.log')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.log_retention_days = int(os.getenv('LOG_RETENTION_DAYS', '5'))

    @property
    def rabbitmq_url(self):
        user = quote(self.rabbitmq_default_user, safe='')
        password = quote(self.rabbitmq_default_pass, safe='')
        return 'amqp://{0}:{1}@{2}:{3}/'.format(
            user,
            password,
            self.rabbitmq_host,
            self.rabbitmq_port
        )


_settings = None


def get_settings():
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
