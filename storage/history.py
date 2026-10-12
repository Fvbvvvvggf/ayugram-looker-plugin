"""
Activity History module
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from storage.database import Database
from utils.logger import get_logger


class ActivityHistory:
    """Manages activity history for users"""
    
    def __init__(self):
        self.logger = get_logger()
        self.db = Database()
    
    def record_activity(self, user_id: int, activity_type: str, 
                       chat_id: Optional[int] = None, 
                       message_id: Optional[int] = None,
                       data: Optional[Dict] = None) -> bool:
        """Record user activity"""
        return self.db.add_activity(user_id, activity_type, chat_id, message_id, data)
    
    def get_user_history(self, user_id: int, hours: int = 24) -> List[Dict]:
        """Get user activity history"""
        return self.db.get_activities(user_id, hours)
    
    def get_activity_count(self, user_id: int, activity_type: Optional[str] = None, hours: int = 24) -> int:
        """Get count of activities"""
        activities = self.get_user_history(user_id, hours)
        
        if activity_type:
            activities = [a for a in activities if a['activity_type'] == activity_type]
        
        return len(activities)
    
    def get_last_activity(self, user_id: int) -> Optional[Dict]:
        """Get last activity for user"""
        activities = self.db.get_activities(user_id, hours=168, limit=1)
        return activities[0] if activities else None
    
    def get_activity_summary(self, user_id: int, hours: int = 24) -> Dict:
        """Get activity summary"""
        activities = self.get_user_history(user_id, hours)
        
        summary = {
            'total_activities': len(activities),
            'by_type': {},
            'last_activity': None,
            'first_activity': None,
            'time_span_hours': hours
        }
        
        if activities:
            for activity in activities:
                activity_type = activity['activity_type']
                summary['by_type'][activity_type] = summary['by_type'].get(activity_type, 0) + 1
            
            summary['last_activity'] = activities[0]['timestamp']
            summary['first_activity'] = activities[-1]['timestamp']
        
        return summary
    
    def get_most_active_time(self, user_id: int, hours: int = 24) -> Optional[str]:
        """Get most active hour of the day"""
        activities = self.get_user_history(user_id, hours)
        
        if not activities:
            return None
        
        hour_counts = {}
        for activity in activities:
            try:
                dt = datetime.fromisoformat(activity['timestamp'])
                hour = dt.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
            except:
                continue
        
        if hour_counts:
            max_hour = max(hour_counts, key=hour_counts.get)
            return f"{max_hour:02d}:00"
        
        return None
    
    def get_activity_timeline(self, user_id: int, hours: int = 24) -> List[Dict]:
        """Get activity timeline"""
        activities = self.get_user_history(user_id, hours)
        timeline = []
        
        for activity in activities:
            timeline.append({
                'type': activity['activity_type'],
                'time': activity['timestamp'],
                'chat_id': activity['chat_id'],
                'message_id': activity['message_id']
            })
        
        return timeline
    
    def is_user_active_now(self, user_id: int, threshold_minutes: int = 5) -> bool:
        """Check if user is active in last N minutes"""
        last_activity = self.get_last_activity(user_id)
        
        if not last_activity:
            return False
        
        try:
            last_time = datetime.fromisoformat(last_activity['timestamp'])
            time_diff = datetime.now() - last_time
            return time_diff.total_seconds() < (threshold_minutes * 60)
        except:
            return False
    
    def get_inactive_users(self, hours: int = 1) -> List[int]:
        """Get users inactive for N hours"""
        # This would need access to all users from database
        # Implementation depends on how watch_list is structured
        pass
    
    def export_history(self, user_id: int, hours: int = 24, format_type: str = 'json') -> str:
        """Export activity history"""
        import json
        activities = self.get_user_history(user_id, hours)
        
        if format_type == 'json':
            return json.dumps(activities, indent=2, default=str)
        
        return str(activities)
