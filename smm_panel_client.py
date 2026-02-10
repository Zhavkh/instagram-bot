"""
Instagram SMM Panel Integration Client
Интеграция с популярными SMM-панелями для быстрого увеличения метрик
"""

import requests
import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ServiceType(Enum):
    """Типы услуг SMM"""
    FOLLOWERS = "followers"
    LIKES = "likes"
    VIEWS = "views"
    COMMENTS = "comments"
    STORY_VIEWS = "story_views"


@dataclass
class OrderStatus:
    """Статус заказа"""
    order_id: str
    status: str
    remains: int
    start_count: int
    currency_count: int


class SMMPanelClient:
    """Клиент для работы с SMM-панелями"""
    
    # Популярные SMM-панели (примеры API endpoints)
    PANELS = {
        'panel1': 'https://api.smmPanel1.com/v2',
        'panel2': 'https://api.smmPanel2.com/v2',
        'panel3': 'https://api.smmPanel3.com/v2',
    }
    
    def __init__(self, api_key: str, panel_name: str = 'panel1'):
        """
        Инициализация клиента
        
        Args:
            api_key: API ключ от SMM-панели
            panel_name: Название панели из списка PANELS
        """
        self.api_key = api_key
        self.base_url = self.PANELS.get(panel_name)
        if not self.base_url:
            raise ValueError(f"Unknown panel: {panel_name}")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def _make_request(self, action: str, params: Dict = None) -> Dict:
        """
        Выполнить запрос к API
        
        Args:
            action: Действие API
            params: Параметры запроса
            
        Returns:
            Ответ от API
        """
        data = {
            'key': self.api_key,
            'action': action
        }
        
        if params:
            data.update(params)
        
        try:
            response = self.session.post(self.base_url, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            return {'error': str(e)}
    
    def get_balance(self) -> float:
        """
        Получить баланс аккаунта
        
        Returns:
            Баланс в USD
        """
        result = self._make_request('balance')
        if 'balance' in result:
            return float(result['balance'])
        return 0.0
    
    def get_services(self) -> List[Dict]:
        """
        Получить список доступных услуг
        
        Returns:
            Список услуг с ценами и описаниями
        """
        result = self._make_request('services')
        if isinstance(result, list):
            return result
        return []
    
    def find_service(self, service_type: ServiceType, 
                     platform: str = 'instagram',
                     quality: str = 'high') -> Optional[Dict]:
        """
        Найти подходящую услугу
        
        Args:
            service_type: Тип услуги
            platform: Платформа (instagram, youtube, etc)
            quality: Качество (high, medium, low)
            
        Returns:
            Информация об услуге или None
        """
        services = self.get_services()
        
        # Фильтруем по критериям
        for service in services:
            name = service.get('name', '').lower()
            category = service.get('category', '').lower()
            
            if (platform.lower() in name and 
                service_type.value in name and
                quality in name):
                return service
        
        # Если не нашли с quality, ищем без него
        for service in services:
            name = service.get('name', '').lower()
            if platform.lower() in name and service_type.value in name:
                return service
        
        return None
    
    def create_order(self, service_id: int, link: str, 
                     quantity: int) -> Optional[str]:
        """
        Создать заказ
        
        Args:
            service_id: ID услуги
            link: Ссылка на профиль/пост
            quantity: Количество (подписчиков, лайков и т.д.)
            
        Returns:
            ID заказа или None при ошибке
        """
        params = {
            'service': service_id,
            'link': link,
            'quantity': quantity
        }
        
        result = self._make_request('add', params)
        
        if 'order' in result:
            return str(result['order'])
        elif 'error' in result:
            print(f"❌ Order creation failed: {result['error']}")
        
        return None
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """
        Получить статус заказа
        
        Args:
            order_id: ID заказа
            
        Returns:
            Статус заказа
        """
        params = {'order': order_id}
        result = self._make_request('status', params)
        
        if 'status' in result:
            return OrderStatus(
                order_id=order_id,
                status=result.get('status', 'Unknown'),
                remains=int(result.get('remains', 0)),
                start_count=int(result.get('start_count', 0)),
                currency_count=int(result.get('currency_count', 0))
            )
        
        return None
    
    def get_multiple_statuses(self, order_ids: List[str]) -> List[OrderStatus]:
        """
        Получить статусы нескольких заказов
        
        Args:
            order_ids: Список ID заказов
            
        Returns:
            Список статусов
        """
        params = {'orders': ','.join(order_ids)}
        result = self._make_request('status', params)
        
        statuses = []
        if isinstance(result, dict):
            for order_id, data in result.items():
                statuses.append(OrderStatus(
                    order_id=order_id,
                    status=data.get('status', 'Unknown'),
                    remains=int(data.get('remains', 0)),
                    start_count=int(data.get('start_count', 0)),
                    currency_count=int(data.get('currency_count', 0))
                ))
        
        return statuses


class InstagramBooster:
    """Высокоуровневый класс для накрутки Instagram"""
    
    def __init__(self, smm_client: SMMPanelClient):
        """
        Args:
            smm_client: Клиент SMM-панели
        """
        self.client = smm_client
    
    def boost_followers(self, username: str, count: int, 
                       quality: str = 'high') -> Optional[str]:
        """
        Накрутить подписчиков
        
        Args:
            username: Instagram username (без @)
            count: Количество подписчиков
            quality: Качество (high/medium/low)
            
        Returns:
            Order ID или None
        """
        # Формируем ссылку на профиль
        profile_link = f"https://www.instagram.com/{username}/"
        
        # Находим подходящую услугу
        service = self.client.find_service(
            ServiceType.FOLLOWERS,
            platform='instagram',
            quality=quality
        )
        
        if not service:
            print("❌ Service not found")
            return None
        
        service_id = service['service']
        price_per_1000 = float(service['rate'])
        total_cost = (count / 1000) * price_per_1000
        
        print(f"📊 Service: {service['name']}")
        print(f"💰 Price: ${price_per_1000} per 1000")
        print(f"💵 Total cost: ${total_cost:.2f}")
        print(f"📦 Quantity: {count}")
        
        # Проверяем баланс
        balance = self.client.get_balance()
        print(f"💳 Your balance: ${balance:.2f}")
        
        if balance < total_cost:
            print(f"❌ Insufficient balance! Need ${total_cost - balance:.2f} more")
            return None
        
        # Создаем заказ
        print(f"\n🚀 Creating order...")
        order_id = self.client.create_order(service_id, profile_link, count)
        
        if order_id:
            print(f"✅ Order created! ID: {order_id}")
            return order_id
        
        return None
    
    def track_order(self, order_id: str, check_interval: int = 30):
        """
        Отслеживать выполнение заказа
        
        Args:
            order_id: ID заказа
            check_interval: Интервал проверки в секундах
        """
        print(f"\n📊 Tracking order {order_id}...")
        print("Press Ctrl+C to stop tracking\n")
        
        try:
            while True:
                status = self.client.get_order_status(order_id)
                
                if status:
                    completed = status.start_count - status.remains
                    progress = (completed / status.start_count * 100) if status.start_count > 0 else 0
                    
                    print(f"Status: {status.status}")
                    print(f"Progress: {completed}/{status.start_count} ({progress:.1f}%)")
                    print(f"Remains: {status.remains}")
                    print(f"Current count: {status.currency_count}")
                    print("-" * 50)
                    
                    if status.status.lower() in ['completed', 'partial', 'canceled']:
                        print(f"\n✅ Order finished with status: {status.status}")
                        break
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n⏸️ Tracking stopped by user")


def main():
    """Пример использования"""
    
    print("=" * 60)
    print("Instagram SMM Panel Booster")
    print("=" * 60)
    
    # ВАЖНО: Замените на ваш реальный API ключ
    API_KEY = "YOUR_API_KEY_HERE"
    PANEL_NAME = "panel1"  # Выберите панель
    
    # Инициализация
    try:
        smm_client = SMMPanelClient(API_KEY, PANEL_NAME)
        booster = InstagramBooster(smm_client)
        
        # Проверяем баланс
        balance = smm_client.get_balance()
        print(f"\n💳 Current balance: ${balance:.2f}\n")
        
        # Параметры заказа
        INSTAGRAM_USERNAME = "your_username"  # Замените на ваш username
        FOLLOWERS_COUNT = 3000
        QUALITY = "high"  # high/medium/low
        
        # Создаем заказ
        order_id = booster.boost_followers(
            username=INSTAGRAM_USERNAME,
            count=FOLLOWERS_COUNT,
            quality=QUALITY
        )
        
        if order_id:
            # Отслеживаем выполнение
            booster.track_order(order_id, check_interval=60)
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
