# redis_db.py
import redis
import os
from dotenv import load_dotenv

load_dotenv()

class RedisDB:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=0,
            decode_responses=True
        )
    
    def add_new_process(self, name_process) -> bool:
        try:
            result = self.redis_client.sadd("process_not_finished", name_process)
            return bool(result)
        except Exception as e:
            print(f"При добавлении не завершенного процесса произошла ошибка: {e}")
            return False
        
    def remove_process(self, name_process) -> bool:
        """
        Удаляет название процесса из множества незавершённых процессов.

        Args:
            name_process (str): название процесса для удаления.

        Returns:
            bool: True, если процесс был удалён; False, если процесса не было или произошла ошибка.
        """
        try:
            result = self.redis_client.srem("process_not_finished", name_process)
            return bool(result)
        except Exception as e:
            print(f"При удалении процесса произошла ошибка: {e}")
            return False
    
    
    

# Создание глобального экземпляра
redis_db = RedisDB()
