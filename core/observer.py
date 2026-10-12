"""
Activity Observer module for tracking user activity
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

from utils.logger import get_logger
from config.config import get_config


class ActivityType(Enum):
    """Types of user activity"""
    MESSAGE_SENT = "message_sent"
    MESSAGE_READ = "message_read"
    TYPING = "typing"
    ONLINE_STATUS = "online_status"
    LAST_SEEN = "last_seen"
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"
    STORY_VIEW = "story_view"
    REACTION = "reaction"


@dataclass
class UserActivity:
    """Represents a single user activity event"""
    user_id: int
    username: str
    activity_type: ActivityType
    timestamp: datetime
    chat_id: Optional[int] = None
    message_id: Optional[int] = None
    data: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'activity_type': self.activity_type.value,
            'timestamp': self.timestamp.isoformat(),
            'chat_id': self.chat_id,
            'message_id': self.message_id,
            'data': self.data
        }


@dataclass
class UserStatus:
    """Current status of a user"""
    user_id: int
    username: str
    last_seen: Optional[datetime] = None
    is_online: bool = False
    activity_count: int = 0
    last_activity_type: Optional[ActivityType] = None
    typing: bool = False
    platform: Optional[str] = None  # mobile, desktop, web
    last_notification_sent: Optional[datetime] = None


class ActivityObserver:
    """Observes and tracks user activity from multiple sources"""
    
    def __init__(self):
        self.logger = get_logger()
        self.config = get_config()
        self.user_activities: Dict[int, List[UserActivity]] = {}
        self.user_statuses: Dict[int, UserStatus] = {}
        self.watched_users: Set[int] = set()
        self.activity_callbacks: List = []
        self.last_update: Optional[datetime] = None
    
    def add_watched_user(self, user_id: int, username: str) -> None:
        """Add user to watch list"""
        self.watched_users.add(user_id)
        if user_id not in self.user_activities:
            self.user_activities[user_id] = []
            self.user_statuses[user_id] = UserStatus(
                user_id=user_id,
                username=username
            )
        self.logger.info(f"Added user to watch: {username} ({user_id})")
    
    def remove_watched_user(self, user_id: int) -> None:
        """Remove user from watch list"""
        if user_id in self.watched_users:
            self.watched_users.remove(user_id)
            self.logger.info(f"Removed user from watch: {user_id}")
    
    def record_activity(self, activity: UserActivity) -> None:
        """Record a user activity event"""
        if activity.user_id not in self.user_activities:
            self.user_activities[activity.user_id] = []
        
        self.user_activities[activity.user_id].append(activity)
        
        # Update user status
        if activity.user_id in self.user_statuses:
            status = self.user_statuses[activity.user_id]
            status.last_seen = activity.timestamp
            status.last_activity_type = activity.activity_type
            status.activity_count += 1
            
            if activity.activity_type == ActivityType.TYPING:
                status.typing = True
            elif activity.activity_type == ActivityType.ONLINE_STATUS:
                status.is_online = activity.data.get('is_online', False)
        
        self.logger.debug(
            f"Activity recorded: {activity.username} - {activity.activity_type.value}"
        )
        
        # Trigger callbacks
        for callback in self.activity_callbacks:
            try:
                callback(activity)
            except Exception as e:
                self.logger.error(f"Error in activity callback: {e}")
    
    def get_user_status(self, user_id: int) -> Optional[UserStatus]:
        """Get current status of user"""
        return self.user_statuses.get(user_id)
    
    def get_user_activities(
        self,
        user_id: int,
        hours: int = 24,
        activity_type: Optional[ActivityType] = None
    ) -> List[UserActivity]:
        """Get user activities from last N hours"""
        if user_id not in self.user_activities:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        activities = [
            a for a in self.user_activities[user_id]
            if a.timestamp > cutoff_time
        ]
        
        if activity_type:
            activities = [a for a in activities if a.activity_type == activity_type]
        
        return activities
    
    def get_activity_summary(self, user_id: int, hours: int = 24) -> Dict:
        """Get activity summary for user"""
        activities = self.get_user_activities(user_id, hours)
        status = self.get_user_status(user_id)
        
        activity_types = {}
        for activity in activities:
            activity_type = activity.activity_type.value
            activity_types[activity_type] = activity_types.get(activity_type, 0) + 1
        
        return {
            'user_id': user_id,
            'username': status.username if status else 'Unknown',
            'total_activities': len(activities),
            'activity_breakdown': activity_types,
            'last_seen': status.last_seen.isoformat() if status and status.last_seen else None,
            'is_online': status.is_online if status else False,
            'typing': status.typing if status else False
        }
    
    def register_callback(self, callback) -> None:
        """Register callback for activity events"""
        self.activity_callbacks.append(callback)
    
    def cleanup_old_activities(self, days: int = 30) -> int:
        """Clean up activities older than N days"""
        cutoff_time = datetime.now() - timedelta(days=days)
        cleaned = 0
        
        for user_id in list(self.user_activities.keys()):
            original_count = len(self.user_activities[user_id])
            self.user_activities[user_id] = [
                a for a in self.user_activities[user_id]
                if a.timestamp > cutoff_time
            ]
            cleaned += original_count - len(self.user_activities[user_id])
        
        self.logger.info(f"Cleaned up {cleaned} old activities")
        return cleaned
    
    async def start_monitoring(self) -> None:
        """Start continuous activity monitoring"""
        self.logger.info("Activity monitoring started")
        
        while self.config.is_enabled:
            try:
                await asyncio.sleep(self.config.update_interval)
                # Cleanup old activities periodically
                if datetime.now().hour == 0:  # Run at midnight
                    history_days = self.config.get('history_days', 30)
                    self.cleanup_old_activities(history_days)
            except Exception as e:
                self.logger.error(f"Error during monitoring: {e}")
    
    def get_watched_users_statuses(self) -> List[UserStatus]:
        """Get statuses of all watched users"""
        return [
            self.user_statuses[uid] for uid in self.watched_users
            if uid in self.user_statuses
        ]
