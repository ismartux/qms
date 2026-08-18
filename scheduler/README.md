# Scheduled Forms - Timeline, Progress & Alert System

## ✅ Implementation Complete

This implementation adds comprehensive timeline visualization, progress tracking, and automated alert notifications for scheduled forms in the QMS system.

---

## 🎯 Features Delivered

### 1. **Timeline & Progress on Form Cards** ✅
The form cards now display rich timeline and progress information:

#### Shift Limit Progress
- **Visual Progress Bar**: Shows completion status (e.g., 2/4 forms filled)
- **Remaining Count**: Displays how many more submissions needed
- **Completion Status**: Shows "✓ Completed for shift" when done
- **Color-coded**: Uses theme colors for visual consistency

#### Interval-Based Timeline
- **Live Progress Bar**: Shows elapsed time vs. interval (e.g., 45/60 min)
- **DUE NOW Badge**: Red alert badge when form is overdue
- **Dynamic Colors**: Progress bar turns red when due
- **Real-time Updates**: Updates on each page load

#### Daily Schedule Status
- **Completion Indicator**: Green checkmark or red warning
- **Clear Status**: "✓ Completed today" or "⚠ Not completed today"
- **Visual Prominence**: Easy to spot at a glance

### 2. **Missed Form Detection** ✅
Automated system to detect and track missed form submissions:

- **Automatic Detection**: Runs every 15 minutes via middleware
- **Smart Detection**: Identifies forms that are past due and not completed
- **Alert Tracking**: Creates `MissedFormAlert` records for each missed instance
- **Duplicate Prevention**: Ensures only one alert per user per instance
- **Auto-Resolution**: Marks alerts as resolved when form is submitted

### 3. **Multi-Channel Notifications** ✅

#### In-App Notifications
- **User Alerts**: Direct notifications to users via EHSNotification model
- **Detailed Messages**: Includes form name, expected time, and action required
- **Persistent**: Stored in database for audit trail

#### Group Chat Alerts (Lark/Feishu)
- **Rich Cards**: Interactive card format with user details
- **Complete Information**: 
  - User name and ID
  - Form name
  - Expected submission time
  - Current status
- **Actionable**: Clear call-to-action for supervisors
- **Webhook-based**: Uses existing LarkConfig infrastructure

---

## 📁 Files Created/Modified

### Core Implementation
| File | Changes | Purpose |
|------|---------|---------|
| `scheduler/models.py` | Modified | Added `MissedFormAlert` model and `is_missed()` method |
| `scheduler/services.py` | Modified | Added detection & alert functions |
| `scheduler/middleware.py` | Modified | Enhanced to run detection every 15 min |
| `scheduler/migrations/0004_missedformalert.py` | Created | Database schema for alerts |
| `scheduler/migrations/0005_*.py` | Created | Auto-generated index fixes |

### UI/UX
| File | Changes | Purpose |
|------|---------|---------|
| `ui/templates/operator/forms_list.html` | Modified | Added timeline & progress sections |

### Management & Documentation
| File | Changes | Purpose |
|------|---------|---------|
| `scheduler/management/commands/detect_missed_forms.py` | Created | Manual detection trigger |
| `scheduler/IMPLEMENTATION_GUIDE.md` | Created | Detailed setup & usage guide |
| `scheduler/README.md` | Created | This summary document |

---

## 🚀 Quick Start

### 1. Database Setup (Already Done ✅)
```bash
cd apps/qms
python3 manage.py makemigrations scheduler
python3 manage.py migrate scheduler
```

### 2. Configure Lark Webhook (Optional)
To enable group alerts, add configuration in Django Admin:

1. Go to `/admin/notifications/larkconfig/`
2. Add new entry:
   - **Name**: `missed_form` (or `alert` as fallback)
   - **Webhook URL**: Your Lark group webhook URL

### 3. Test the System

#### Manual Testing
```bash
# Run detection manually
python3 manage.py detect_missed_forms

# Dry run (no alerts sent)
python3 manage.py detect_missed_forms --dry-run
```

#### View Results
1. Check form cards at: `ui/forms_list` - See timeline & progress
2. Check alerts at: `/admin/scheduler/missedformalert/`
3. Monitor notifications in Lark group (if configured)

---

## 🎨 How It Looks

### Form Card Example (Shift Limit)
```
┌─────────────────────────────────────┐
│ [Form Safety Checklist]        v2.0 │
│ Shift Progress                      │
│ ████████████░░░░░░  2/4             │
│ 2 remaining                         │
└─────────────────────────────────────┘
```

### Form Card Example (Interval)
```
┌─────────────────────────────────────┐
│ [Equipment Check]               v1.0│
│ Next Due                     DUE NOW│
│ ██████████████████  45/60 min       │
│ Elapsed: 45 minutes                 │
└─────────────────────────────────────┘
```

### Form Card Example (Daily)
```
┌─────────────────────────────────────┐
│ [Daily Inspection]              v3.0│
│ Daily Target                        │
│ ✓ Completed today                   │
└─────────────────────────────────────┘
```

---

## 🔧 Configuration

### Adjust Detection Frequency
Edit `scheduler/middleware.py`:
```python
self._missed_check_interval = 15 * 60  # Change 15 to desired minutes
```

### Customize Alert Messages
Edit `scheduler/services.py`:
- `send_missed_form_notification()` - In-app message
- `send_group_alert()` - Lark card format

### User Assignment Logic
Current: Alerts all users with active work contexts

To customize, edit `detect_and_alert_missed_forms()`:
```python
# Filter by role
active_contexts = active_contexts.filter(
    user__profile__role__code='OPERATOR'
)

# Filter by plant
active_contexts = active_contexts.filter(
    plant=specific_plant
)
```

---

## 📊 Monitoring & Analytics

### Check Missed Alerts
```python
from scheduler.models import MissedFormAlert

# All alerts
alerts = MissedFormAlert.objects.all()

# Unresolved alerts
unresolved = MissedFormAlert.objects.filter(notification_sent=False)

# User-specific
user_alerts = MissedFormAlert.objects.filter(user=user)

# Recent alerts (last 24 hours)
from django.utils import timezone
from datetime import timedelta
recent = MissedFormAlert.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=24)
)
```

### Admin Dashboard
Access at: `/admin/scheduler/missedformalert/`

Features:
- Filter by user, date, notification status
- Bulk actions for alert management
- Search and export capabilities

---

## 🔍 Troubleshooting

### Progress Not Showing
1. ✅ Ensure form has schedule configured in admin
2. ✅ Verify schedule type is set correctly
3. ✅ Check submissions are being recorded
4. ✅ Verify user has proper role assignments

### Alerts Not Sending
1. ✅ Check Lark webhook configuration
2. ✅ Verify network connectivity
3. ✅ Check Django logs for errors
4. ✅ Ensure middleware is active

### Middleware Not Running
1. ✅ Verify in `settings.py` MIDDLEWARE list
2. ✅ Check middleware order (should be early)
3. ✅ Ensure users are authenticated
4. ✅ Check server logs for errors

---

## 📈 Benefits

### For Operators
- ✅ Clear visibility of form requirements
- ✅ Real-time progress tracking
- ✅ Reduced missed submissions
- ✅ Better shift management

### For Supervisors
- ✅ Automated alerting for missed forms
- ✅ Group chat notifications for quick action
- ✅ Complete audit trail
- ✅ Reduced manual monitoring

### For Organization
- ✅ Improved compliance
- ✅ Better quality control
- ✅ Reduced operational risk
- ✅ Data-driven insights

---

## 🔮 Future Enhancements

Potential additions for future iterations:

- [ ] **Escalation System**: Auto-escalate repeatedly missed forms
- [ ] **Grace Period**: Configurable buffer before marking as missed
- [ ] **Email Notifications**: Add email as alternative channel
- [ ] **Analytics Dashboard**: Visual reports on form completion rates
- [ ] **Bulk Actions**: Reassign missed forms in bulk
- [ ] **User Preferences**: Let users customize notification settings
- [ ] **Mobile Push**: Send push notifications to mobile app
- [ ] **SMS Alerts**: Critical alerts via SMS for key personnel

---

## 📝 Notes

- **Backward Compatible**: Existing schedules continue to work
- **No Breaking Changes**: All existing functionality preserved
- **Performance Optimized**: Throttled detection to avoid overhead
- **Production Ready**: Includes error handling and logging
- **Well Documented**: Comprehensive guides and inline comments

---

## 🆘 Support

For issues or questions:
1. Check `IMPLEMENTATION_GUIDE.md` for detailed documentation
2. Review Django logs for error messages
3. Verify configuration in Django Admin
4. Test with management command before deploying

---

## ✨ Summary

This implementation provides a complete solution for:
- ✅ **Visual timeline** on form cards
- ✅ **Progress tracking** (shift limit, interval, daily)
- ✅ **Missed form detection** (automatic, every 15 min)
- ✅ **Multi-channel alerts** (in-app + Lark group chat)
- ✅ **Production-ready** with error handling and monitoring

The system is now live and will automatically track form submissions, display progress, and alert stakeholders when forms are missed.