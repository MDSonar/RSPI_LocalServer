# Dark Mode Standards for RSPI LocalServer Apps

## Overview
All apps in RSPI LocalServer must follow a unified dark mode design. This ensures consistency across the dashboard and all installed applications.

## Color Palette

### Backgrounds
- **Primary Gradient**: `linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)`
- **Card/Container**: `rgba(30, 30, 46, 0.9)` with `1px solid rgba(255, 255, 255, 0.1)` border
- **Hover/Focus**: `rgba(102, 126, 234, 0.1)` or `rgba(102, 126, 234, 0.3)` for selected
- **Dark Overlay**: `rgba(0, 0, 0, 0.3)` for nested elements

### Text
- **Primary Text**: `#e0e0e8`
- **Secondary Text**: `#d0d0d8`
- **Muted Text**: `#a0a0b0` (for labels)
- **Disabled Text**: `#9090a0`

### Accents
- **Primary**: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- **Success**: `rgba(52, 211, 153, 0.2)` background with `#86efac` text
- **Error**: `rgba(248, 113, 113, 0.2)` background with `#fca5a5` text
- **Warning**: `#f39c12`

## Button Styles

### Primary Button
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
color: white;
```

### Secondary Button
```css
background: rgba(255, 255, 255, 0.15);
color: #d0d0d8;
```

### Danger Button
```css
background: #dc3545;
color: white;
```

## Border & Shadows

### Standard Border
```css
border: 1px solid rgba(255, 255, 255, 0.1);
```

### Card Shadow
```css
box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
```

### Focus Shadow
```css
box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
```

## Input Fields

```css
background: rgba(0, 0, 0, 0.3);
border: 1px solid rgba(255, 255, 255, 0.2);
color: #e0e0e8;
```

### Placeholder
```css
color: #9090a0;
```

## Structure Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>App Name</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            padding: 20px;
            color: #e0e0e8;
        }

        .container { max-width: 1200px; margin: 0 auto; }

        header {
            background: rgba(30, 30, 46, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
            text-align: center;
        }

        h1 {
            font-size: 24px;
            background: linear-gradient(135deg, #667eea 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .card {
            background: rgba(30, 30, 46, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
        }

        button {
            padding: 10px 16px;
            border: none;
            border-radius: 8px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            cursor: pointer;
            font-weight: 600;
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>App Name</h1>
        </header>
        <!-- App content -->
    </div>
</body>
</html>
```

## Implementation Checklist

When creating a new app:
- [ ] Use dark gradient background: `linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)`
- [ ] Apply dark card styling with borders and shadows
- [ ] Use light text colors from the palette
- [ ] Style all buttons with primary/secondary/danger variants
- [ ] Add hover states with appropriate shadows/colors
- [ ] Style all input fields with dark backgrounds
- [ ] Use alert/status styles for success/error/warning messages
- [ ] Test on both desktop and mobile views
- [ ] Ensure all links and interactive elements have clear hover states

## Assets
- Dashboard: [app/static/dashboard.html](app/static/dashboard.html)
- File Manager: [app/static/filemanager.html](app/static/filemanager.html)
- System Info: [app/static/systeminfo.html](app/static/systeminfo.html)
- Task Manager: [app/static/taskmanager.html](app/static/taskmanager.html)

## Support
For consistency questions, refer to the dashboard implementation as the canonical reference.
