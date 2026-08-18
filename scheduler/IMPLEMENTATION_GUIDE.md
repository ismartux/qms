# Scheduled Forms - Timeline & Progress Tracking Implementation

## Overview
This implementation adds timeline visualization, progress tracking, and missed form alert notifications to the QMS scheduled forms system.

## Features Implemented

### 1. Timeline & Progress Display on Form Cards
- **Shift Limit Progress**: Shows completed/total count with progress bar
  - Example: "2/4" with visual progress bar
  - Shows remaining count or "Completed for shift" status
  
- **Interval-Based Timeline**: 
  - Shows elapsed/total minutes
  - Visual progress bar that turns red when due
  - "DUE NOW" badge when form needs to be filled
  
- **Daily Schedule Status**:
  - Shows whether form is completed for the day
  - Visual indicators (green checkmark or red warning)

### 2. Missed Form Detection
- Automatically detects when scheduled forms are not submitted on time
- Runs every 15 minutes via middleware
- Creates `MissedFormAlert` records for tracking

### 3. Notification System
- **In-App Notifications**: Uses EHSNotification model to alert users
- **Group Alerts**: Sends formatted alerts to Lark/Feishu group chat via webhook
  - Includes user name, user ID, form name, expected time
  - Uses interactive card format for better visibility

## Files Modified/Created

### Models
- `scheduler/models.py` - Added `MissedFormAlert` model and `is_missed()` method

### Services
- `scheduler/services.py` - Added:
  - `detect_and_alert_missed_forms()` - Main detection logic
  - `send_missed_form_notification()` - In-app notification sender
  - `send_group_alert()` - Lark group chat alert sender
  - Updated `mark_instance_completed()` to resolve alerts

### Middleware
- `scheduler/middleware.py` - Enhanced to run missed form detection every 15 minutes

### Templates
- `ui/templates/operator/forms_list.html` - Added timeline and progress sections

### Migrations
- `scheduler/migrations/0004_missedformalert.py` - Database schema for alerts

### Management Commands
- `scheduler/management/commands/detect_missed_forms.py` - Manual detection trigger

## Setup Instructions

### 1. Run Migrations
```bash
cd apps/qms
python manage.py makemigrations scheduler
python manage.py migrate
```

### 2. Configure Lark Webhook (Optional)
To enable group alerts, add a LarkConfig entry in Django Admin:
- Name: "missed_form" (or "alert" as fallback)
- Webhook URL: Your Lark group webhook URL

### 3. Test the Implementation

#### Manual Testing
```bash
# Run missed form detection manually
python manage.py detect_missed_forms

# Dry run (no alerts sent)
python manage.py detect_missed_forms --dry-run
```

#### Automated Testing
The middleware automatically runs detection every 15 minutes when users access the system.

## How It Works

### Form Card Display
When a user views the forms list:
1. View logic calculates progress for each scheduled form
2. For shift_limit: Counts submissions vs. required count
3. For interval/daily: Calculates time elapsed and next due time
4. Template renders visual progress bars and status indicators

### Missed Form Detection Flow
1. Middleware triggers detection every 15 minutes
2. Finds all ScheduledInstances where:
   - `is_completed = False`
   - `expected_at <= now` (past due)
3. For each missed instance:
   - Creates MissedFormAlert record
   - Sends in-app notification to user
   - Sends group alert to Lark (if configured)
4. When form is eventually submitted:
   - Alert is marked as resolved

## Configuration

### Adjusting Detection Frequency
Edit `scheduler/middleware.py`:
```python
self._missed_check_interval = 15 * 60  # Change 15 to desired minutes
```

### Customizing Alert Messages
Edit the message templates in `scheduler/services.py`:
- `send_missed_form_notification()` - In-app message
- `send_group_alert()` - Lark card format

### User Assignment Logic
The current implementation alerts all users with active work contexts. To customize:
Edit `detect_and_alert_missed_forms()` in `scheduler/services.py` to filter users based on:
- Specific roles
- Plant/shop/line assignments
- Other business rules

## Monitoring

### Check Missed Alerts
```python
from scheduler.models import MissedFormAlert

# View all missed alerts
alerts = MissedFormAlert.objects.all()

# View unresolved alerts
unresolved = MissedFormAlert.objects.filter(notification_sent=False)

# View alerts for specific user
user_alerts = MissedFormAlert.objects.filter(user=user)
```

### Admin Interface
Access via Django Admin:
- `/admin/scheduler/missedformalert/` - View all missed form alerts
- Filter by user, notification status, date range

## Troubleshooting

### Alerts Not Being Sent
1. Check Lark webhook configuration in admin
2. Verify network connectivity to Lark API
3. Check Django logs for errors

### Progress Not Showing
1. Ensure form has a schedule configured
2. Verify schedule type matches the progress being displayed
3. Check that submissions are being recorded correctly

### Middleware Not Running
1. Ensure middleware is in `settings.py` MIDDLEWARE list
2. Check that users are authenticated
3. Verify middleware order (should be early in stack)

## Future Enhancements

- [ ] Add escalation for repeatedly missed forms
- [ ] Configurable grace period before marking as missed
- [ ] Email notifications in addition to Lark
- [ ] Dashboard for missed form analytics
- [ ] Bulk reassignment of missed forms
- [ ] User-specific notification preferences