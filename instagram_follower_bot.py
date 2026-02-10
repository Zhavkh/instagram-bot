"""
Instagram Follow/Unfollow Bot (Clean Mode)
Только подписки и отписки - без лайков и комментариев
"""

import time
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import instagrapi
from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, 
    ChallengeRequired,
    PleaseWaitFewMinutes,
    RateLimitError
)


class FollowerBot:
    """Бот для накрутки подписчиков через Follow/Unfollow"""
    
    def __init__(self, username: str, password: str, session_file: str = "session.json"):
        """
        Args:
            username: Instagram username
            password: Instagram password
            session_file: Файл для сохранения сессии
        """
        self.username = username
        self.password = password
        self.session_file = session_file
        self.client = Client()
        
        # Статистика
        self.stats = {
            'followed_today': 0,
            'unfollowed_today': 0,
            'followers_gained': 0,
            'start_followers': 0,
            'current_followers': 0
        }
        
        # База данных подписок (кого мы подписали)
        self.followed_users = self._load_followed_users()
        
        # Whitelist - защита существующих подписок/подписчиков
        self.whitelist = self._load_whitelist()
        
    def _load_followed_users(self) -> Dict:
        """Загрузить список подписанных пользователей"""
        try:
            with open('followed_users.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def _save_followed_users(self):
        """Сохранить список подписанных пользователей"""
        with open('followed_users.json', 'w') as f:
            json.dump(self.followed_users, f, indent=2)
    
    def _load_whitelist(self) -> Dict:
        """Загрузить whitelist (защищенные пользователи)"""
        try:
            with open('whitelist.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'followers': [],  # Ваши подписчики
                'following': [],  # Ваши подписки
                'custom': []      # Дополнительные защищенные
            }
    
    def _save_whitelist(self):
        """Сохранить whitelist"""
        with open('whitelist.json', 'w') as f:
            json.dump(self.whitelist, f, indent=2)
    
    def _build_whitelist(self):
        """
        Построить whitelist из текущих подписчиков и подписок
        ВАЖНО: Вызывать ОДИН РАЗ при первом запуске!
        """
        print("🛡️ Building whitelist (protecting existing followers/following)...")
        
        try:
            user_id = self.client.user_id_from_username(self.username)
            
            # Получаем всех подписчиков
            print("📥 Fetching your followers...")
            followers = self.client.user_followers(user_id)
            self.whitelist['followers'] = [str(uid) for uid in followers.keys()]
            
            # Получаем всех подписок
            print("📤 Fetching your following...")
            following = self.client.user_following(user_id)
            self.whitelist['following'] = [str(uid) for uid in following.keys()]
            
            # Сохраняем
            self._save_whitelist()
            
            print(f"✅ Whitelist built:")
            print(f"   - Followers protected: {len(self.whitelist['followers'])}")
            print(f"   - Following protected: {len(self.whitelist['following'])}")
            print(f"   - Total protected: {len(self.whitelist['followers']) + len(self.whitelist['following'])}")
            
        except Exception as e:
            print(f"❌ Error building whitelist: {e}")
    
    def _is_whitelisted(self, user_id: int) -> bool:
        """
        Проверить, находится ли пользователь в whitelist
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если пользователь защищен
        """
        user_id_str = str(user_id)
        return (
            user_id_str in self.whitelist['followers'] or
            user_id_str in self.whitelist['following'] or
            user_id_str in self.whitelist['custom']
        )
    
    def login(self):
        """Авторизация в Instagram"""
        print(f"🔐 Logging in as @{self.username}...")
        
        try:
            # Попытка загрузить сессию
            try:
                self.client.load_settings(self.session_file)
                self.client.login(self.username, self.password)
                print("✅ Logged in using saved session")
            except:
                # Новая авторизация
                self.client.login(self.username, self.password)
                self.client.dump_settings(self.session_file)
                print("✅ Logged in and saved session")
            
            # Получаем начальное количество подписчиков
            user_info = self.client.user_info_by_username(self.username)
            self.stats['start_followers'] = user_info.follower_count
            self.stats['current_followers'] = user_info.follower_count
            
            print(f"📊 Current followers: {self.stats['current_followers']}")
            
            # Проверяем whitelist
            if not self.whitelist['followers'] and not self.whitelist['following']:
                print("\n⚠️ Whitelist is empty. Building whitelist to protect existing connections...")
                self._build_whitelist()
            else:
                print(f"\n🛡️ Whitelist loaded: {len(self.whitelist['followers']) + len(self.whitelist['following'])} users protected")
            
        except ChallengeRequired:
            print("⚠️ Instagram requires verification. Check your email/SMS.")
            raise
        except Exception as e:
            print(f"❌ Login failed: {e}")
            raise
    
    def find_target_users(self, target_username: str, limit: int = 50) -> List[int]:
        """
        Найти целевых пользователей (подписчиков конкурента)
        
        Args:
            target_username: Username конкурента/похожего аккаунта
            limit: Сколько пользователей получить
            
        Returns:
            Список user_id (исключая whitelist)
        """
        print(f"🔍 Finding users from @{target_username}...")
        
        try:
            target_user_id = self.client.user_id_from_username(target_username)
            followers = self.client.user_followers(target_user_id, amount=limit * 2)  # Берем больше для фильтрации
            
            # Фильтруем whitelist
            user_ids = [
                uid for uid in followers.keys() 
                if not self._is_whitelisted(uid)
            ]
            
            # Ограничиваем до нужного количества
            user_ids = user_ids[:limit]
            
            print(f"✅ Found {len(user_ids)} potential targets (excluded {len(followers) - len(user_ids)} whitelisted)")
            return user_ids
            
        except Exception as e:
            print(f"❌ Error finding users: {e}")
            return []
    
    def find_users_by_hashtag(self, hashtag: str, limit: int = 50) -> List[int]:
        """
        Найти пользователей по хештегу
        
        Args:
            hashtag: Хештег (без #)
            limit: Сколько пользователей получить
            
        Returns:
            Список user_id (исключая whitelist)
        """
        print(f"🔍 Finding users by #{hashtag}...")
        
        try:
            medias = self.client.hashtag_medias_recent(hashtag, amount=limit * 2)  # Берем больше для фильтрации
            user_ids = [media.user.pk for media in medias]
            user_ids = list(set(user_ids))  # Убираем дубликаты
            
            # Фильтруем whitelist
            user_ids = [
                uid for uid in user_ids 
                if not self._is_whitelisted(uid)
            ]
            
            # Ограничиваем до нужного количества
            user_ids = user_ids[:limit]
            
            print(f"✅ Found {len(user_ids)} users (excluded whitelisted)")
            return user_ids
            
        except Exception as e:
            print(f"❌ Error finding users: {e}")
            return []
    
    def follow_user(self, user_id: int) -> bool:
        """
        Подписаться на пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если успешно
        """
        try:
            # Проверяем whitelist (защита существующих связей)
            if self._is_whitelisted(user_id):
                print(f"🛡️ User {user_id} is whitelisted, skipping...")
                return False
            
            # Проверяем, не подписаны ли уже
            if str(user_id) in self.followed_users:
                return False
            
            # Подписываемся
            self.client.user_follow(user_id)
            
            # Сохраняем в базу
            self.followed_users[str(user_id)] = {
                'followed_at': datetime.now().isoformat(),
                'unfollowed': False
            }
            self._save_followed_users()
            
            self.stats['followed_today'] += 1
            
            user_info = self.client.user_info(user_id)
            print(f"✅ Followed @{user_info.username}")
            
            return True
            
        except PleaseWaitFewMinutes:
            print("⚠️ Rate limit! Waiting 5 minutes...")
            time.sleep(300)
            return False
        except Exception as e:
            print(f"❌ Follow error: {e}")
            return False
    
    def unfollow_user(self, user_id: int) -> bool:
        """
        Отписаться от пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если успешно
        """
        try:
            # КРИТИЧЕСКАЯ ЗАЩИТА: НИКОГДА не отписываемся от whitelist
            if self._is_whitelisted(user_id):
                print(f"🛡️ User {user_id} is whitelisted, NEVER unfollowing!")
                return False
            
            self.client.user_unfollow(user_id)
            
            # Обновляем базу
            if str(user_id) in self.followed_users:
                self.followed_users[str(user_id)]['unfollowed'] = True
                self.followed_users[str(user_id)]['unfollowed_at'] = datetime.now().isoformat()
                self._save_followed_users()
            
            self.stats['unfollowed_today'] += 1
            
            user_info = self.client.user_info(user_id)
            print(f"➖ Unfollowed @{user_info.username}")
            
            return True
            
        except Exception as e:
            print(f"❌ Unfollow error: {e}")
            return False
    
    def unfollow_non_followers(self, days_ago: int = 3, limit: int = 50):
        """
        Отписаться от тех, кто не подписался обратно
        
        Args:
            days_ago: Отписываться от тех, кого подписали N дней назад
            limit: Максимум отписок
        """
        print(f"\n🔄 Unfollowing users who didn't follow back (>{days_ago} days)...")
        
        cutoff_date = datetime.now() - timedelta(days=days_ago)
        unfollowed_count = 0
        
        for user_id, data in list(self.followed_users.items()):
            if unfollowed_count >= limit:
                break
            
            # Пропускаем уже отписанных
            if data.get('unfollowed', False):
                continue
            
            # ЗАЩИТА: Пропускаем whitelist
            user_id_int = int(user_id)
            if self._is_whitelisted(user_id_int):
                continue
            
            # Проверяем дату подписки
            followed_at = datetime.fromisoformat(data['followed_at'])
            if followed_at > cutoff_date:
                continue
            
            # Проверяем, подписан ли пользователь на нас
            try:
                friendship = self.client.user_friendship(user_id_int)
                
                # Если не подписан на нас - отписываемся
                if not friendship.followed_by:
                    self.unfollow_user(user_id_int)
                    unfollowed_count += 1
                    
                    # Задержка между отписками
                    delay = random.randint(30, 60)
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"⚠️ Error checking user {user_id}: {e}")
                continue
        
        print(f"✅ Unfollowed {unfollowed_count} users")
    
    def run_follow_campaign(self, 
                           target_sources: List[Dict],
                           follows_per_session: int = 50,
                           delay_range: tuple = (30, 60)):
        """
        Запустить кампанию подписок
        
        Args:
            target_sources: Список источников целевой аудитории
                [{'type': 'user', 'value': 'username'}, {'type': 'hashtag', 'value': 'tag'}]
            follows_per_session: Сколько подписок за сессию
            delay_range: Диапазон задержки между подписками (сек)
        """
        print(f"\n🚀 Starting follow campaign...")
        print(f"Target: {follows_per_session} follows")
        
        all_targets = []
        
        # Собираем целевых пользователей из всех источников
        for source in target_sources:
            if source['type'] == 'user':
                users = self.find_target_users(source['value'], limit=100)
                all_targets.extend(users)
            elif source['type'] == 'hashtag':
                users = self.find_users_by_hashtag(source['value'], limit=100)
                all_targets.extend(users)
        
        # Перемешиваем и берем нужное количество
        random.shuffle(all_targets)
        all_targets = all_targets[:follows_per_session]
        
        print(f"📋 Total targets collected: {len(all_targets)}")
        
        # Подписываемся
        followed_count = 0
        for user_id in all_targets:
            if self.follow_user(user_id):
                followed_count += 1
                
                # Случайная задержка
                delay = random.randint(delay_range[0], delay_range[1])
                print(f"⏳ Waiting {delay}s...")
                time.sleep(delay)
        
        print(f"\n✅ Campaign finished! Followed {followed_count} users")
        self.print_stats()
    
    def print_stats(self):
        """Вывести статистику"""
        # Обновляем текущее количество подписчиков
        try:
            user_info = self.client.user_info_by_username(self.username)
            self.stats['current_followers'] = user_info.follower_count
            self.stats['followers_gained'] = (
                self.stats['current_followers'] - self.stats['start_followers']
            )
        except:
            pass
        
        print("\n" + "="*50)
        print("📊 SESSION STATISTICS")
        print("="*50)
        print(f"Followed today: {self.stats['followed_today']}")
        print(f"Unfollowed today: {self.stats['unfollowed_today']}")
        print(f"Start followers: {self.stats['start_followers']}")
        print(f"Current followers: {self.stats['current_followers']}")
        print(f"Gained: +{self.stats['followers_gained']}")
        print("="*50 + "\n")


def main():
    """Пример использования"""
    
    print("="*60)
    print("Instagram Follow/Unfollow Bot (Clean Mode)")
    print("="*60)
    
    # НАСТРОЙКИ - ЗАМЕНИТЕ НА СВОИ!
    USERNAME = "your_username"
    PASSWORD = "your_password"
    
    # Источники целевой аудитории
    TARGET_SOURCES = [
        {'type': 'user', 'value': 'competitor_username'},  # Подписчики конкурента
        {'type': 'hashtag', 'value': 'yourtopic'},         # Пользователи по хештегу
    ]
    
    # Режимы работы
    MODES = {
        'safe': {
            'follows_per_session': 30,
            'delay_range': (60, 120),
            'description': 'Безопасный (30 подписок, 60-120 сек задержка)'
        },
        'moderate': {
            'follows_per_session': 50,
            'delay_range': (40, 80),
            'description': 'Умеренный (50 подписок, 40-80 сек задержка)'
        },
        'aggressive': {
            'follows_per_session': 100,
            'delay_range': (30, 60),
            'description': 'Агрессивный (100 подписок, 30-60 сек задержка)'
        }
    }
    
    # Выберите режим
    MODE = 'moderate'  # safe / moderate / aggressive
    
    try:
        # Инициализация
        bot = FollowerBot(USERNAME, PASSWORD)
        bot.login()
        
        # Запуск кампании подписок
        print(f"\n🎯 Mode: {MODES[MODE]['description']}")
        bot.run_follow_campaign(
            target_sources=TARGET_SOURCES,
            follows_per_session=MODES[MODE]['follows_per_session'],
            delay_range=MODES[MODE]['delay_range']
        )
        
        # Отписка от неактивных (опционально)
        # bot.unfollow_non_followers(days_ago=3, limit=50)
        
        print("\n✅ Bot finished successfully!")
        
    except KeyboardInterrupt:
        print("\n⏸️ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
