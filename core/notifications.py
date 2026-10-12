"""
Notification Manager for user activity alerts
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio

from utils.logger import get_logger
from config.config import get_config


class NotificationType(Enum):
    """Types of notifications"""
    USER_CAME_ONLINE = "user_came_online"
    USER_WENT_OFFLINE = "user_went_offline"
    USER_TYPING = "user_typing"
    USER_READ_MESSAGE = "user_read_message"
    HIGH_ACTIVITY = "high_activity"
    UNUSUAL_PATTERN = "unusual_pattern"


@dataclass
class Notification:
    """Represents a notification event"""
    notification_type: NotificationType
    user_id: int
    username: str
    message: str
    timestamp: datetime
    data: Dict = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}


class NotificationManager:
    """Manages notifications for user activity"""
    
    def __init__(self):
        self.logger = get_logger()
        self.config = get_config()
        self.notifications: List[Notification] = []
        self.notification_callbacks: List[Callable] = []
        self.user_last_notification: Dict[int, datetime] = {}
        self.notification_queue: asyncio.Queue = asyncio.Queue()
        self.enabled = self.config.notifications_enabled
    
    def enable_notifications(self) -> None:
        """Enable notifications"""
        self.enabled = True
        self.config.set('notifications_enabled', True)
        self.logger.info("Notifications enabled")
    
    def disable_notifications(self) -> None:
        """Disable notifications"""
        self.enabled = False
        self.config.set('notifications_enabled', False)
        self.logger.info("Notifications disabled")
    
    def should_notify_user(self, user_id: int, min_interval_minutes: int = 5) -> bool:
        """
        Check if enough time has passed since last notification for this user
        
        Args:
            user_id: User ID
            min_interval_minutes: Minimum interval between notifications
            
        Returns:
            True if notification should be sent
        """
        last_notification = self.user_last_notification.get(user_id)
        
        if last_notification is None:
            return True
        
        time_diff = datetime.now() - last_notification
        return time_diff.total_seconds() >= (min_interval_minutes * 60)
    
    def send_notification(
        self,
        notification_type: NotificationType,
        user_id: int,
        username: str,
        message: str,
        data: Optional[Dict] = None
    ) -> bool:
        """
        Send a notification
        
        Args:
            notification_type: Type of notification
            user_id: User ID
            username: Username
            message: Notification message
            data: Additional data
            
        Returns:
            True if notification was sent
        """
        if not self.enabled:
            return False
        
        # Check notification interval
        if not self.should_notify_user(user_id):
            self.logger.debug(f"Skipping notification for {username} - too soon")
            return False
        
        # Check if user is in whitelist/blacklist
        whitelist = self.config.whitelist
        blacklist = self.config.blacklist
        
        if whitelist and user_id not in whitelist and username not in [str(u) for u in whitelist]:
            return False
        
        if blacklist and (user_id in blacklist or username in [str(u) for u in blacklist]):
            return False
        
        notification = Notification(
            notification_type=notification_type,
            user_id=user_id,
            username=username,
            message=message,
            timestamp=datetime.now(),
            data=data or {}
        )
        
        self.notifications.append(notification)
        self.user_last_notification[user_id] = datetime.now()
        
        self.logger.info(f"Notification sent: {message}")
        
        # Trigger callbacks
        for callback in self.notification_callbacks:
            try:
                asyncio.create_task(callback(notification)) if asyncio.iscoroutinefunction(callback) else callback(notification)
            except Exception as e:
                self.logger.error(f"Error in notification callback: {e}")
        
        return True
    
    def register_callback(self, callback: Callable) -> None:
        """Register callback for notifications"""
        self.notification_callbacks.append(callback)
    
    def get_notifications(
        self,
        user_id: Optional[int] = None,
        hours: int = 24,
        notification_type: Optional[NotificationType] = None
    ) -> List[Notification]:
        """
        Get notifications
        
        Args:
            user_id: Filter by user ID
            hours: Only notifications from last N hours
            notification_type: Filter by notification type
            
        Returns:
            List of notifications
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        notifications = [
            n for n in self.notifications
            if n.timestamp > cutoff_time
        ]
        
        if user_id is not None:
            notifications = [n for n in notifications if n.user_id == user_id]
        
        if notification_type is not None:
            notifications = [n for n in notifications if n.notification_type == notification_type]
        
        return notifications
    
    def get_recent_notifications(self, limit: int = 10) -> List[Notification]:
        """Get most recent notifications"""
        return sorted(self.notifications, key=lambda n: n.timestamp, reverse=True)[:limit]
    
    def clear_notifications(self, older_than_hours: int = 72) -> int:
        """Clear old notifications"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        original_count = len(self.notifications)
        self.notifications = [n for n in self.notifications if n.timestamp > cutoff_time]
        cleared = original_count - len(self.notifications)
        self.logger.info(f"Cleared {cleared} old notifications")
        return cleared
    
    def get_notification_stats(self) -> Dict:
        """Get notification statistics"""
        stats = {
            'total_notifications': len(self.notifications),
            'enabled': self.enabled,
            'by_type': {},
            'by_user': {}
        }
        
        for notification in self.notifications:
            # Count by type
            type_key = notification.notification_type.value
            stats['by_type'][type_key] = stats['by_type'].get(type_key, 0) + 1
            
            # Count by user
            user_key = f"{notification.username}({notification.user_id})"
            stats['by_user'][user_key] = stats['by_user'].get(user_key, 0) + 1
        
        return stats
