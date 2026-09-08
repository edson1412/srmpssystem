# Malawi Prison Service - Template Restructuring Guide

## Overview

The MPS management system has been restructured with a unified dashboard architecture supporting both Prison (inmates management) and HRMS (officers management) modules through a single, well-organized template hierarchy.

## Architecture

### Template Hierarchy

```
base.html (Main unified dashboard template)
├── prison/
│   ├── base.html (extends base.html)
│   ├── dashboard.html (Prison-specific dashboard, extends prison/base.html)
│   └── [other prison templates]
├── hrms/
│   ├── dashboard.html (HRMS-specific dashboard, extends base.html)
│   └── [other HRMS templates]
└── accounts/
    ├── dashboard_choice.html (Dual-access user dashboard selection page)
    └── [other auth templates]
```

## Key Files

### 1. **templates/base.html** (Main Base Template)
- **Purpose**: Unified dashboard base for both modules
- **Features**:
  - Fixed collapsible sidebar navigation
  - Top header with user info and notifications
  - Role-based navigation items
  - Responsive design for mobile and desktop
  - Main content area with proper padding and styling

- **Navigation Structure**:
  - Dashboard link
  - **Officers Management** (HRMS section)
    - HRMS Dashboard
    - Officers Directory
    - Training Wing
    - ICT Management
  - **Inmates Management** (Prison section)
    - Release Hub
    - Prisoners (with submenu)
    - Visitors (with submenu)
    - Medical (with submenu)
    - Rations (with submenu)
    - Biometrics (with submenu)
    - Reports (with submenu)
  - **Administration** (Superuser only)
    - Prison Stations
    - User Management
  - **Sidebar Footer**
    - Change Password
    - Logout

### 2. **static/css/dashboard.css**
- **Purpose**: All dashboard-specific styling
- **Contains**:
  - CSS variables for colors and spacing
  - Sidebar styles (brand, navigation, footer)
  - Top header styles
  - Responsive media queries
  - Notification system styling
  - Alert and message styling

### 3. **prison/templates/prison/base.html**
- **Purpose**: Prison module base template
- **Current Implementation**: Extends main base.html
- **Use**: All prison module templates extend this file

### 4. **prison/templates/prison/dashboard.html**
- **Purpose**: Prison dashboard main page
- **Extends**: prison/base.html
- **Features**:
  - Stat cards (prisoners, admissions, releases, etc.)
  - Dashboard-specific styles and animations
  - Charts and data visualizations

### 5. **hrms/templates/hrms/dashboard.html**
- **Purpose**: HRMS/Officers dashboard main page
- **Extends**: base.html
- **Features**:
  - Officer statistics and metrics
  - Performance indicators
  - Training program cards
  - HR-specific content

### 6. **templates/accounts/dashboard_choice.html**
- **Purpose**: Dual-access user dashboard selection page
- **Features**:
  - Beautiful card-based UI showing available dashboards
  - Prison and HRMS dashboard options with descriptions
  - Feature lists for each dashboard
  - Smooth animations and hover effects
  - Responsive grid layout

## User Roles and Access

### Single-Access Users
- **Prison Roles**: Admin, Reception, Station Officer, Visitor Attendant, Medical Officer, Superuser
- **HRMS Roles**: National Commissioner, National HR, Regional HR, Station HR, Training Wing Officer, etc.

When these users log in, they are automatically redirected to their role-specific primary dashboard.

### Dual-Access Users
- **Officer in Charge** (OIC)
- **Regional Commanding Officer** (RCO)
- **Regional Headquarters Officer** (RHO)

When these users log in, they see a dashboard choice page allowing them to select between:
- **Prison Dashboard**: Access to inmate management features
- **HRMS Dashboard**: Access to officer management features

## Sidebar Navigation Features

### Collapsible Sidebar
- **Desktop**: Always visible, can be toggled
- **Mobile**: Hidden by default, opens on hamburger menu click
- **Width**: 280px (desktop), collapses to 0px on mobile
- **Overlay**: Semi-transparent overlay closes sidebar on mobile

### Navigation Items
- **Module Sections**: Color-coded for easy identification
  - Prison items: Green color scheme (#10b981)
  - HRMS items: Purple color scheme (#8b5cf6)
- **Active States**: Highlighted with module-specific colors
- **Expandable Menus**: Chevron icons indicate collapsible sections

### Sidebar User Info
- User's full name
- User's role (color-coded)
- Prison station assignment (if applicable)

## Top Header Features

### Left Section
- **Hamburger Menu**: Toggle sidebar visibility
- **Page Title**: Current page/section name

### Right Section
- **Notifications**: Bell icon with unread count badge
  - Dropdown with notification list
  - Mark all as read button
  - View all notifications link
- **User Dropdown**:
  - User avatar
  - User name and role (visible on medium+ screens)
  - Profile link
  - Change password link
  - Logout link

## Routing and Login Flow

### Login Process
1. User enters credentials on login page
2. Django authenticates the user
3. System checks user roles:
   - **Dual-access user**: Redirected to `/accounts/dashboard-choice/`
   - **Single-access user**: Redirected to their primary dashboard
4. User selects dashboard (if dual-access) or lands on primary dashboard

### Dashboard URLs
- **Prison Dashboard**: `/` (primary prison dashboard)
- **HRMS Dashboard**: `/hr/` (primary HRMS dashboard)
- **Dashboard Choice**: `/accounts/dashboard-choice/` (for dual-access users)

## User Model Helper Methods

### New Methods Added

```python
def get_all_dashboard_urls()
    """Get all accessible dashboard URLs for this user"""
    Returns list of dicts with 'name', 'url_name', and 'module' keys

def has_dual_dashboards()
    """Check if user has access to multiple dashboards"""
    Returns boolean
```

### Existing Methods Used

```python
@property
can_access_hrms
    """Check if user can access HRMS module"""

@property
can_access_prison
    """Check if user can access Prison module"""

@property
is_dual_access_user
    """Check if user has dual module access"""

@property
primary_module
    """Get primary module for this user"""

def get_landing_url_name()
    """Get the landing URL name for this user's primary dashboard"""
```

## Styling System

### Color Variables (CSS)
```css
--sidebar-width: 280px
--header-height: 70px
--primary-color: #1a73e8
--sidebar-bg: #0f172a
--hrms-color: #8b5cf6
--prison-color: #10b981
```

### Responsive Breakpoints
- **992px**: Sidebar collapses on tablets
- **576px**: Additional mobile optimizations
  - Reduced padding
  - Hidden role labels
  - Simplified header

### Key CSS Classes
- `.sidebar-wrapper`: Main sidebar container
- `.nav-link`: Navigation items
- `.nav-link.active`: Active navigation state
- `.top-header`: Fixed header bar
- `.main-content`: Main content area
- `.sidebar-overlay`: Mobile overlay

## Template Inheritance Chain

### Prison Module
```
prison/dashboard.html
    └── prison/base.html
            └── base.html (main template)
```

### HRMS Module
```
hrms/dashboard.html
    └── base.html (main template)
```

### Dual-Access Page
```
dashboard_choice.html
    └── base.html (main template)
```

## Navigation Guards

The sidebar navigation automatically shows/hides items based on user roles:

```django
{% if request.user.can_access_hrms %}
    <!-- Show HRMS navigation items -->
{% endif %}

{% if request.user.can_access_prison %}
    <!-- Show Prison navigation items -->
{% endif %}

{% if request.user.is_super_admin %}
    <!-- Show admin-only items -->
{% endif %}
```

## Messages and Alerts

All alert messages are styled consistently using Bootstrap utilities:
- `.alert-success`: Green background (#dcfce7)
- `.alert-danger`: Red background (#fee2e2)
- `.alert-warning`: Yellow background (#fef3c7)
- `.alert-info`: Blue background (#dbeafe)

## Notifications System

The notifications dropdown displays:
- Unread notification count badge
- List of recent notifications with:
  - Priority indicator (colored dot)
  - Notification type badge
  - Message and timestamp
  - Hover effects for better UX

## JavaScript Functionality

### Sidebar Toggle
```javascript
// File: static/js/scripts.js
// Handles sidebar show/hide on mobile
document.getElementById('sidebarToggle').addEventListener('click', function() {
    document.body.classList.toggle('sidebar-collapsed');
    document.getElementById('sidebarOverlay').classList.toggle('show');
});
```

### Notifications Loading
```javascript
// Loads notification count every 30 seconds
function loadNotifications() {
    fetch('/notifications/count/')
        .then(response => response.json())
        .then(data => updateNotificationBadge(data.count));
}

setInterval(loadNotifications, 30000);
```

## File Organization

```
mps-active/
├── templates/
│   ├── base.html                    # Main unified dashboard
│   ├── accounts/
│   │   ├── dashboard_choice.html   # Dual-access choice page
│   │   ├── login.html
│   │   └── [other auth templates]
│   ├── prison/
│   │   ├── base.html               # Prison module base
│   │   └── [prison templates]
│   └── hrms/
│       └── [hrms templates]
├── static/
│   ├── css/
│   │   ├── dashboard.css           # Dashboard styling
│   │   └── [other styles]
│   ├── js/
│   │   └── scripts.js              # Dashboard JS
│   └── [other assets]
├── prison/
│   ├── templates/
│   │   └── prison/
│   │       ├── base.html
│   │       ├── dashboard.html
│   │       └── [other templates]
│   └── [prison app files]
├── hrms/
│   ├── templates/
│   │   └── hrms/
│   │       ├── dashboard.html
│   │       └── [other templates]
│   └── [hrms app files]
└── accounts/
    ├── models.py                   # User model with helper methods
    ├── views.py                    # Updated with dashboard_choice_view
    ├── routing.py                  # Updated routing logic
    └── [other auth files]
```

## Migration Guide

### For Existing Templates

1. **Prison templates**: Update extends statement
   ```django
   <!-- Old -->
   {% extends "prison/base.html" %}
   
   <!-- New (automatically handled since prison/base.html extends base.html) -->
   {% extends "prison/base.html" %}
   ```

2. **HRMS templates**: Already extending base.html, no changes needed

3. **Custom pages**: Simply use:
   ```django
   {% extends "base.html" %}
   ```

## Performance Considerations

### CSS
- All styles consolidated in `dashboard.css` for faster loading
- Media queries optimize for responsive design
- Smooth transitions use CSS instead of JavaScript

### JavaScript
- Minimal JavaScript footprint
- Event delegation for efficient DOM manipulation
- Lazy loading of notifications

### Sidebar
- CSS Grid for flexible menu layout
- Flexbox for alignment
- Fixed positioning avoids layout reflows

## Browser Support

- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions
- Mobile browsers: iOS Safari 12+, Chrome for Android

## Customization

### Changing Sidebar Width
Edit `dashboard.css`:
```css
:root {
    --sidebar-width: 320px; /* Change from 280px */
}
```

### Changing Color Scheme
Edit `dashboard.css` CSS variables:
```css
:root {
    --primary-color: #your-color;
    --hrms-color: #your-color;
    --prison-color: #your-color;
}
```

### Adding New Navigation Items
Edit `templates/base.html` sidebar nav section:
```django
{% if request.user.has_permission %}
<a href="{% url 'your_url' %}" class="nav-link">
    <i class="bi bi-icon-name"></i> Label
</a>
{% endif %}
```

## Troubleshooting

### Sidebar Not Showing
- Check browser console for JavaScript errors
- Verify CSS file is loading (check Network tab)
- Ensure user has proper permissions

### Navigation Items Missing
- Check user role and permissions
- Verify `can_access_hrms` or `can_access_prison` properties
- Check Django template conditional logic

### Dashboard Choice Not Showing
- Verify user has `is_dual_access_user` property returning True
- Check that `has_dual_dashboards()` method is returning True
- Ensure URL routing includes `dashboard_choice` path

## Future Enhancements

Potential improvements:
1. Dark mode toggle
2. Sidebar menu search functionality
3. Quick action buttons in header
4. Custom user dashboard widgets
5. Theme customization for different prisons
6. Advanced notification filtering
7. Keyboard shortcuts for navigation

## Support

For issues or questions about the template structure:
1. Check this documentation
2. Review the code comments in template files
3. Contact the development team

---

**Last Updated**: August 2026
**Version**: 1.0
**Author**: Development Team
