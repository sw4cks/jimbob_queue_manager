import sqlite3
import os
from datetime import datetime
from typing import List, Tuple

class QueueDatabase:
    def __init__(self, db_path: str = 'queue.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create queue table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                added_by TEXT NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Create users table for tracking contributions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                items_added INTEGER DEFAULT 0,
                last_added TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_to_queue(self, title: str, category: str, user_id: str, username: str) -> int:
        """Add an item to the queue and return the item ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO queue (title, category, added_by)
                VALUES (?, ?, ?)
            ''', (title, category, user_id))
            
            item_id = cursor.lastrowid
            
            # Update user stats
            cursor.execute('''
                INSERT INTO users (user_id, username, items_added, last_added)
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    items_added = items_added + 1,
                    last_added = CURRENT_TIMESTAMP
            ''', (user_id, username))
            
            conn.commit()
            conn.close()
            return item_id
        except Exception as e:
            print(f"Error adding to queue: {e}")
            return None
    
    def get_queue(self, category: str = None) -> List[Tuple]:
        """Get all items from the queue, optionally filtered by category"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if category:
                cursor.execute('''
                    SELECT id, title, category, added_by, added_date, status
                    FROM queue
                    WHERE status = 'pending' AND category = ?
                    ORDER BY added_date
                ''', (category,))
            else:
                cursor.execute('''
                    SELECT id, title, category, added_by, added_date, status
                    FROM queue
                    WHERE status = 'pending'
                    ORDER BY added_date
                ''')
            
            results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            print(f"Error getting queue: {e}")
            return []
    
    def remove_from_queue(self, item_id: int) -> bool:
        """Remove or mark an item as completed"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE queue
                SET status = 'completed'
                WHERE id = ?
            ''', (item_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error removing from queue: {e}")
            return False
    
    def get_item(self, item_id: int):
        """Fetch a single queue item by id"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, title, category, added_by, status
                FROM queue
                WHERE id = ?
            ''', (item_id,))
            
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            print(f"Error fetching item: {e}")
            return None
    
    def undo_last_entry(self, user_id: str) -> Tuple:
        """Remove the last entry added by a user and return the item info"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get the last pending item added by this user
            cursor.execute('''
                SELECT id, title, category
                FROM queue
                WHERE added_by = ? AND status = 'pending'
                ORDER BY added_date DESC
                LIMIT 1
            ''', (user_id,))
            
            result = cursor.fetchone()
            
            if result:
                item_id = result[0]
                # Delete the item
                cursor.execute('DELETE FROM queue WHERE id = ?', (item_id,))
                
                # Update user stats
                cursor.execute('''
                    UPDATE users
                    SET items_added = items_added - 1
                    WHERE user_id = ?
                ''', (user_id,))
                
                conn.commit()
                conn.close()
                return result
            
            conn.close()
            return None
        except Exception as e:
            print(f"Error undoing entry: {e}")
            return None
    
    def get_user_stats(self, user_id: str) -> Tuple:
        """Get user contribution statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT username, items_added, last_added
                FROM users
                WHERE user_id = ?
            ''', (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return None
    
    def get_queue_stats(self) -> dict:
        """Get overall queue statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM queue WHERE status = "pending"')
            pending = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM queue WHERE status = "completed"')
            completed = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM queue
                WHERE status = 'pending'
                GROUP BY category
            ''')
            by_category = cursor.fetchall()
            
            conn.close()
            
            return {
                'pending': pending,
                'completed': completed,
                'by_category': {cat: count for cat, count in by_category}
            }
        except Exception as e:
            print(f"Error getting queue stats: {e}")
            return {}
