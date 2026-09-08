# Notification System Setup Guide

## Overview
This document describes the notification system that has been added to the Prison Management System for real-time notifications regarding:
- Medical checkup reminders
- Prisoners near release
- Newly admitted prisoners

## Changes Made

### 1. Database Model (`prison/models.py`)
Added `Notification` model with the following features:
- **Notification Types**: medical_checkup, near_release, new_admission, general
- **Priority Levels**: low, medium, high, urgent
- **Status Tracking**: read/unread status, read timestamps
- **Related Objects**: Links to prisoners and medical records
- **Target Users**: Many-to-many relationship to users
- **Action Tracking**: Action required flags and URLs
- **Expiration**: Optional expiration dates

### 2. Notification Utilities (`prison/utils.py`)
Added notification generation functions:
- `create_medical_checkup_notifications()`: Creates notifications for checkups due within 7 days
- `create_near_release_notifications()`: Creates notifications for prisoners due for release within 30 days
- `create_new_admission_notification(prisoner)`: Creates notification when new prisoner is admitted
- `generate_all_notifications()`: Runs all notification generation functions

### 3. View Functions (`prison/views.py`)
Added notification API endpoints:
- `notification_list()`: Returns notifications for current user (JSON)
- `mark_notification_read()`: Marks specific notification as read
- `mark_all_notifications_read()`: Marks all user notifications as read
- `notification_count()`: Returns unread notification count

### 4. URL Configuration (`prison/urls.py`)
Added notification URL patterns:
- `/notifications/` - List notifications
- `/notifications/<id>/read/` - Mark notification as read
- `/notifications/read-all/` - Mark all as read
- `/notifications/count/` - Get unread count

### 5. UI Components (`prison/templates/prison/base.html`)
Added notification interface:
- Notification bell icon with badge counter
- Dropdown notification panel
- Real-time notification loading
- Priority indicators and type badges
- Mark all as read functionality
- Auto-refresh every minute

### 6. Management Command (`prison/management/commands/generate_notifications.py`)
Added Django management command to generate notifications:
```bash
python manage.py generate_notifications
```

### 7. Integration with Prisoner Creation (`prison/views.py`)
Modified `add_prisoner()` function to automatically create notifications when new prisoners are admitted.

## Installation Steps

### 1. Activate Virtual Environment
```bash
# If using virtual environment
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

### 2. Create Database Migrations
```bash
python manage.py makemigrations prison
```

### 3. Apply Migrations
```bash
python manage.py migrate
```

### 4. Test the System
```bash
# Generate notifications manually
python manage.py generate_notifications
```

## Usage

### Manual Notification Generation
Run the management command to generate notifications:
```bash
python manage.py generate_notifications
```

### Automated Scheduling (Recommended)
Set up a cron job or scheduled task to run the notification generation command periodically:

**Linux Cron (every hour):**
```bash
0 * * * * cd /path/to/mps-active && /path/to/venv/bin/python manage.py generate_notifications
```

**Windows Task Scheduler:**
- Create a task to run `python manage.py generate_notifications` hourly
- Set working directory to project directory

### Real-time Notifications
The notification system includes JavaScript that:
- Loads notifications when the bell icon is clicked
- Updates the unread count badge
- Auto-refreshes the count every minute
- Marks notifications as read when clicked
- Navigates to relevant pages when action URLs are available

## Notification Types

### Medical Checkup Notifications
- **Trigger**: Medical records with `next_checkup` date within 7 days
- **Priority**: 
  - Urgent: Checkup due today or tomorrow
  - High: Checkup due within 3 days
  - Medium: Checkup due within 7 days
- **Recipients**: Medical staff users
- **Expiration**: 1 day after checkup date

### Near Release Notifications
- **Trigger**: Convicted prisoners with `date_of_release` within 30 days
- **Priority**:
  - Urgent: Release within 7 days
  - High: Release within 14 days
  - Medium: Release within 30 days
- **Recipients**: Administrative staff
- **Expiration**: 7 days after release date

### New Admission Notifications
- **Trigger**: New prisoner creation
- **Priority**: High
- **Recipients**: Administrative staff
- **Expiration**: 7 days after admission

## Customization

### Adjust Notification Thresholds
Edit the functions in `prison/utils.py` to change timeframes:

```python
# Medical checkups: Change from 7 days
next_week = today + timedelta(days=7)  # Change days value

# Near release: Change from 30 days
next_month = today + timedelta(days=30)  # Change days value
```

### Change Recipient Users
Modify the user filtering in notification functions:

```python
# Current: All staff users
medical_staff = User.objects.filter(is_staff=True)

# Example: Medical officers only
medical_staff = User.objects.filter(role='medical_officer')
```

### Adjust Auto-refresh Interval
In `base.html`, change the interval:
```javascript
setInterval(() => this.updateNotificationCount(), 60000); // 60000ms = 1 minute
```

## Troubleshooting

### Notifications Not Appearing
1. Check that the management command is running
2. Verify users have correct permissions
3. Check browser console for JavaScript errors
4. Ensure CSRF tokens are working

### Badge Count Not Updating
1. Check the `/notifications/count/` endpoint is responding
2. Verify JavaScript is executing
3. Check browser network tab for failed requests

### Database Migration Issues
```bash
# If migration fails, try:
python manage.py makemigrations prison --empty
python manage.py migrate prison --fake
python manage.py makemigrations prison
python manage.py migrate
```

## Future Enhancements

Consider adding:
- Email notifications for urgent items
- SMS notifications for critical alerts
- User notification preferences
- Notification history and archiving
- Dashboard notification widget
- Sound notifications for urgent items