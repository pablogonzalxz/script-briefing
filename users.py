import json
import os
from datetime import datetime
from typing import Dict
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DAILY_LIMIT = int(os.getenv("DEFAULT_DAILY_LIMIT", "5"))
DEFAULT_MONTHLY_LIMIT = int(os.getenv("DEFAULT_MONTHLY_LIMIT", "50"))
USERS_DATA_FILE = "users_data.json"

@dataclass
class UserUsage:
    user_id: str
    daily_count: int = 0
    monthly_count: int = 0
    last_reset_date: str = ""
    last_monthly_reset: str = ""
    daily_limit: int = DEFAULT_DAILY_LIMIT
    monthly_limit: int = DEFAULT_MONTHLY_LIMIT
    is_premium: bool = False
    created_at: str = ""
    last_activity: str = ""

class UserManager:
    def __init__(self, data_file: str = USERS_DATA_FILE):
        self.data_file = data_file
        self.users: Dict[str, UserUsage] = {}
        self.load_users()
    
    def load_users(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = {
                        user_id: UserUsage(**user_data) 
                        for user_id, user_data in data.items()
                    }
        except Exception as e:
            print(f"Error loading users data: {e}")
            self.users = {}
    
    def save_users(self):
        try:
            data = {
                user_id: asdict(user_usage) 
                for user_id, user_usage in self.users.items()
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving users data: {e}")
    
    def get_or_create_user(self, user_id: str) -> UserUsage:
        if user_id not in self.users:
            now = datetime.now().isoformat()
            self.users[user_id] = UserUsage(
                user_id=user_id,
                created_at=now,
                last_activity=now,
                last_reset_date=datetime.now().date().isoformat(),
                last_monthly_reset=datetime.now().replace(day=1).date().isoformat()
            )
            self.save_users()
        return self.users[user_id]
    
    def reset_daily_count_if_needed(self, user: UserUsage):
        today = datetime.now().date().isoformat()
        if user.last_reset_date != today:
            user.daily_count = 0
            user.last_reset_date = today
    
    def reset_monthly_count_if_needed(self, user: UserUsage):
        current_month_start = datetime.now().replace(day=1).date().isoformat()
        if user.last_monthly_reset != current_month_start:
            user.monthly_count = 0
            user.last_monthly_reset = current_month_start
    
    def can_user_send_message(self, user_id: str) -> tuple[bool, str]:
        user = self.get_or_create_user(user_id)
        
        self.reset_daily_count_if_needed(user)
        self.reset_monthly_count_if_needed(user)
        
        if user.daily_count >= user.daily_limit:
            return False, f"vc atingiu o limite diário de {user.daily_limit} mensagens. Tente novamente amanhã."
        
        if user.monthly_count >= user.monthly_limit:
            return False, f"vc atingiu o limite mensal de {user.monthly_limit} mensagens. Tente novamente no próximo mês."
        
        return True, "OK"
    
    def increment_usage(self, user_id: str):
        user = self.get_or_create_user(user_id)
        user.daily_count += 1
        user.monthly_count += 1
        user.last_activity = datetime.now().isoformat()
        self.save_users()
    
    def get_user_stats(self, user_id: str) -> dict:
        user = self.get_or_create_user(user_id)
        self.reset_daily_count_if_needed(user)
        self.reset_monthly_count_if_needed(user)
        
        return {
            "user_id": user_id,
            "daily_usage": f"{user.daily_count}/{user.daily_limit}",
            "monthly_usage": f"{user.monthly_count}/{user.monthly_limit}",
            "is_premium": user.is_premium,
            "created_at": user.created_at,
            "last_activity": user.last_activity
        }
    
    def set_user_limits(self, user_id: str, daily_limit: int = None, monthly_limit: int = None):
        user = self.get_or_create_user(user_id)
        if daily_limit is not None:
            user.daily_limit = daily_limit
        if monthly_limit is not None:
            user.monthly_limit = monthly_limit
        self.save_users()
    
    def set_premium_user(self, user_id: str, is_premium: bool = True):
        user = self.get_or_create_user(user_id)
        user.is_premium = is_premium
        if is_premium:
            user.daily_limit = int(os.getenv("PREMIUM_DAILY_LIMIT", "50"))
            user.monthly_limit = int(os.getenv("PREMIUM_MONTHLY_LIMIT", "500"))
        else:
            user.daily_limit = DEFAULT_DAILY_LIMIT
            user.monthly_limit = DEFAULT_MONTHLY_LIMIT
        self.save_users()