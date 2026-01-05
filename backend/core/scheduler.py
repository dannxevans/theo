"""
Proactive Notifications Scheduler

Background job scheduler for proactive calendar and email awareness.
Uses APScheduler to run periodic checks based on user-configurable settings.
"""

import logging
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from typing import Optional

logger = logging.getLogger(__name__)


class ProactiveScheduler:
    """
    Manages background jobs for proactive notifications.

    Jobs are configured based on user settings and run at configurable intervals.
    """

    def __init__(self, memory_store):
        """
        Initialize the proactive scheduler.

        Args:
            memory_store: MemoryStore instance for database access
        """
        self.memory = memory_store
        self.scheduler = BackgroundScheduler(
            daemon=True,
            timezone='UTC',
            job_defaults={
                'coalesce': True,  # If multiple instances are pending, only run once
                'max_instances': 1,  # Only one instance of each job at a time
                'misfire_grace_time': 300  # Allow 5 minutes grace for missed jobs
            }
        )
        self._running = False

        logger.info("[SCHEDULER] Proactive scheduler initialized")

    def start(self):
        """Start the scheduler and schedule jobs based on user settings."""
        if self._running:
            logger.warning("[SCHEDULER] Scheduler already running")
            return

        try:
            # Load user settings to configure job frequencies
            settings = self._load_settings()

            # Schedule jobs based on settings
            self._schedule_calendar_job(settings)
            self._schedule_email_job(settings)
            self._schedule_digest_job(settings)
            self._schedule_cleanup_job()

            # Schedule WHOOP jobs
            self._schedule_whoop_jobs()

            # Start the scheduler
            self.scheduler.start()
            self._running = True

            logger.info("[SCHEDULER] Proactive scheduler started successfully")
            logger.info(f"[SCHEDULER] Active jobs: {len(self.scheduler.get_jobs())}")

        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to start scheduler: {e}")
            raise

    def stop(self):
        """Stop the scheduler gracefully."""
        if not self._running:
            logger.warning("[SCHEDULER] Scheduler not running")
            return

        try:
            self.scheduler.shutdown(wait=True)
            self._running = False
            logger.info("[SCHEDULER] Proactive scheduler stopped")
        except Exception as e:
            logger.error(f"[SCHEDULER] Error stopping scheduler: {e}")

    def is_running(self):
        """Check if scheduler is running."""
        return self._running and self.scheduler.running

    def get_job_status(self):
        """
        Get status of all scheduled jobs.

        Returns:
            dict: Job status information
        """
        if not self.is_running():
            return {
                "running": False,
                "jobs": []
            }

        jobs = []
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None
            })

        return {
            "running": True,
            "jobs": jobs
        }

    def reschedule_jobs(self):
        """
        Reschedule jobs based on updated user settings.
        Called when user changes proactive settings.
        """
        if not self._running:
            logger.warning("[SCHEDULER] Cannot reschedule - scheduler not running")
            return

        try:
            # Remove existing jobs
            for job in self.scheduler.get_jobs():
                job.remove()

            # Load updated settings
            settings = self._load_settings()

            # Reschedule all jobs
            self._schedule_calendar_job(settings)
            self._schedule_email_job(settings)
            self._schedule_digest_job(settings)
            self._schedule_cleanup_job()

            logger.info("[SCHEDULER] Jobs rescheduled successfully")

        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to reschedule jobs: {e}")

    def _load_settings(self):
        """
        Load proactive settings from database.

        Returns:
            dict: User settings with defaults
        """
        try:
            from sqlalchemy import text

            with self.memory.engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT calendar_enabled, calendar_check_frequency_minutes,
                               email_enabled, email_check_frequency_minutes,
                               email_digest_frequency_minutes
                        FROM proactive_settings
                        WHERE user_id = :user_id
                    """),
                    {"user_id": DEFAULT_USER_ID}
                )

                row = result.fetchone()

                if row:
                    return {
                        'calendar_enabled': bool(row[0]),
                        'calendar_check_frequency': row[1],
                        'email_enabled': bool(row[2]),
                        'email_check_frequency': row[3],
                        'digest_frequency': row[4]
                    }
                else:
                    # Return defaults if no settings found
                    return {
                        'calendar_enabled': True,
                        'calendar_check_frequency': 15,
                        'email_enabled': True,
                        'email_check_frequency': 15,
                        'digest_frequency': 60
                    }

        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to load settings: {e}")
            # Return defaults on error
            return {
                'calendar_enabled': True,
                'calendar_check_frequency': 15,
                'email_enabled': True,
                'email_check_frequency': 15,
                'digest_frequency': 60
            }

    def _schedule_calendar_job(self, settings):
        """Schedule calendar monitoring job."""
        if not settings['calendar_enabled']:
            logger.info("[SCHEDULER] Calendar monitoring disabled in settings")
            return

        frequency = settings['calendar_check_frequency']

        # Import here to avoid circular imports
        from core.proactive.calendar_service import check_calendar_events

        # Schedule based on frequency
        if frequency == 15:
            # Use cron for specific times (:00, :15, :30, :45)
            self.scheduler.add_job(
                func=check_calendar_events,
                trigger=CronTrigger(minute='0,15,30,45'),
                id='calendar_check',
                name='Calendar Event Check',
                args=[self.memory]
            )
            logger.info("[SCHEDULER] Calendar job scheduled (every 15 min: :00, :15, :30, :45)")
        else:
            # Use interval trigger for custom frequencies
            self.scheduler.add_job(
                func=check_calendar_events,
                trigger=IntervalTrigger(minutes=frequency),
                id='calendar_check',
                name='Calendar Event Check',
                args=[self.memory]
            )
            logger.info(f"[SCHEDULER] Calendar job scheduled (every {frequency} minutes)")

    def _schedule_email_job(self, settings):
        """Schedule email monitoring job."""
        if not settings['email_enabled']:
            logger.info("[SCHEDULER] Email monitoring disabled in settings")
            return

        frequency = settings['email_check_frequency']

        # Import here to avoid circular imports
        from core.proactive.email_service import check_important_emails

        # Schedule based on frequency
        if frequency == 15:
            # Use cron for specific times (:00, :15, :30, :45)
            self.scheduler.add_job(
                func=check_important_emails,
                trigger=CronTrigger(minute='0,15,30,45'),
                id='email_check',
                name='Important Email Check',
                args=[self.memory]
            )
            logger.info("[SCHEDULER] Email job scheduled (every 15 min: :00, :15, :30, :45)")
        else:
            # Use interval trigger for custom frequencies
            self.scheduler.add_job(
                func=check_important_emails,
                trigger=IntervalTrigger(minutes=frequency),
                id='email_check',
                name='Important Email Check',
                args=[self.memory]
            )
            logger.info(f"[SCHEDULER] Email job scheduled (every {frequency} minutes)")

    def _schedule_digest_job(self, settings):
        """Schedule email digest job."""
        if not settings['email_enabled']:
            logger.info("[SCHEDULER] Email digest disabled (email monitoring disabled)")
            return

        frequency = settings['digest_frequency']

        # Import here to avoid circular imports
        from core.proactive.email_service import send_email_digest

        # Schedule based on frequency
        if frequency == 60:
            # Use cron for hourly at top of hour
            self.scheduler.add_job(
                func=send_email_digest,
                trigger=CronTrigger(minute='0'),
                id='email_digest',
                name='Email Digest',
                args=[self.memory]
            )
            logger.info("[SCHEDULER] Digest job scheduled (hourly at :00)")
        else:
            # Use interval trigger for custom frequencies
            self.scheduler.add_job(
                func=send_email_digest,
                trigger=IntervalTrigger(minutes=frequency),
                id='email_digest',
                name='Email Digest',
                args=[self.memory]
            )
            logger.info(f"[SCHEDULER] Digest job scheduled (every {frequency} minutes)")

    def _schedule_cleanup_job(self):
        """Schedule daily cleanup job for old notification records."""
        # Import here to avoid circular imports
        from core.proactive.cleanup_service import cleanup_old_notifications

        # Run daily at 3 AM UTC
        self.scheduler.add_job(
            func=cleanup_old_notifications,
            trigger=CronTrigger(hour=3, minute=0),
            id='notification_cleanup',
            name='Notification Cleanup',
            args=[self.memory]
        )
        logger.info("[SCHEDULER] Cleanup job scheduled (daily at 03:00 UTC)")

    def _schedule_whoop_jobs(self):
        """Schedule WHOOP notification jobs for all users with WHOOP connected."""
        # Import here to avoid circular imports
        from core.proactive.whoop_sleep_service import WHOOPSleepService
        from core.proactive.whoop_workout_service import WHOOPWorkoutService
        from core.proactive.whoop_stress_service import WHOOPStressService

        # Get all users with WHOOP credentials
        try:
            # For now, check default user (can be expanded to multi-user)
            user_id = DEFAULT_USER_ID
            settings = self.memory.get_whoop_settings(user_id)

            if not settings:
                logger.debug("[SCHEDULER] No WHOOP settings found, skipping WHOOP jobs")
                return

            frequency = settings.get('check_frequency_minutes', 30)

            # Create service instances
            sleep_service = WHOOPSleepService(self.memory)
            workout_service = WHOOPWorkoutService(self.memory)
            stress_service = WHOOPStressService(self.memory)

            # Schedule sleep notifications (check periodically)
            self.scheduler.add_job(
                func=lambda: sleep_service.check_and_notify(user_id),
                trigger=IntervalTrigger(minutes=frequency),
                id='whoop_sleep',
                name='WHOOP Sleep Notifications',
                replace_existing=True
            )
            logger.info(f"[SCHEDULER] WHOOP sleep job scheduled (every {frequency} minutes)")

            # Schedule workout notifications (check periodically)
            self.scheduler.add_job(
                func=lambda: workout_service.check_and_notify(user_id),
                trigger=IntervalTrigger(minutes=frequency),
                id='whoop_workout',
                name='WHOOP Workout Notifications',
                replace_existing=True
            )
            logger.info(f"[SCHEDULER] WHOOP workout job scheduled (every {frequency} minutes)")

            # Schedule stress notifications (daily at user-configured time)
            stress_time = settings.get('stress_notification_time', '14:00')
            hour, minute = stress_time.split(':')
            self.scheduler.add_job(
                func=lambda: stress_service.check_and_notify(user_id),
                trigger=CronTrigger(hour=int(hour), minute=int(minute)),
                id='whoop_stress',
                name='WHOOP Stress Notifications',
                replace_existing=True
            )
            logger.info(f"[SCHEDULER] WHOOP stress job scheduled (daily at {stress_time} UTC)")

        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to schedule WHOOP jobs: {e}")


# Global scheduler instance
_scheduler_instance: Optional[ProactiveScheduler] = None


def init_scheduler(memory_store):
    """
    Initialize and start the global scheduler instance.

    Args:
        memory_store: MemoryStore instance
    """
    global _scheduler_instance

    if _scheduler_instance is not None:
        logger.warning("[SCHEDULER] Scheduler already initialized")
        return _scheduler_instance

    _scheduler_instance = ProactiveScheduler(memory_store)
    _scheduler_instance.start()

    return _scheduler_instance


def get_scheduler():
    """
    Get the global scheduler instance.

    Returns:
        ProactiveScheduler instance or None if not initialized
    """
    return _scheduler_instance


def shutdown_scheduler():
    """Shutdown the global scheduler instance."""
    global _scheduler_instance

    if _scheduler_instance is not None:
        _scheduler_instance.stop()
        _scheduler_instance = None
