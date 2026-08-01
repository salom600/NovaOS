# NovaOS Theming Guide

This document describes how the NovaOS theme system works and how to customise
every visual aspect of the distribution.

## The three layers

NovaOS uses a **three-layer** theming model that matches the user's journey
from power-on to a working desktop:

| Layer | Component              | File                                                                        |
|-------|------------------------|-----------------------------------------------------------------------------|
| 1     | Boot splash (KSplash)  | `archiso/novaos/airootfs/usr/share/plasma/look-and-feel/com.novaos.desktop/contents/splash/Splash.qml` |
| 2     | Login (SDDM)           | `archiso/novaos/airootfs/usr/share/sddm/themes/novaos/Main.qml`            |
| 3     | Desktop (Plasma 6)     | Multiple - see below.                                                       |

### Layer 1 - Boot splash

The boot splash is a QML file rendered by Plasma's KSplashQML engine.  It
runs from the moment systemd hands control to the display manager until SDDM
is ready to show the login screen.

The NovaOS splash renders:

- A vertical gradient background (`#0A0E1C` -> `#0E1422` -> `#060810`).
- A second, slowly-rotating horizontal gradient for the "nebula" effect.
- 32 floating particle dots that drift upward with random opacity.
- The NovaOS logo (SVG) at center, scaled in from 0.6x with a glowing
  blue drop-shadow.
- A thin progress bar that reflects `progress` (provided by KSplashQML).
- The text "Hello. Just a moment..." with a pulsing opacity animation.
- A footer reading "NovaOS 2026.1 - Crystal Glass".

To customise:

1. Edit `Splash.qml`.
2. Replace `images/novaos-logo.svg` with your own SVG (recommended size:
   256x256, viewBox-aligned).
3. Change the colors in the gradient stops.
4. Test locally with `ksplashqml --test com.novaos.desktop`.

### Layer 2 - Login (SDDM)

The login screen is the most complex theme component.  It is a single QML
file (`Main.qml`) that handles two sub-layers:

#### Sub-layer 2a: Greeting

When SDDM first loads, the theme shows:

- The animated video wallpaper (`assets/wallpaper.mp4`).
- A dim gradient overlay for readability.
- The NovaOS logo with a fade-in scale animation.
- "Welcome to NovaOS" in large text.
- "Hello. Just a moment..." in lighter text with a blinking ellipsis.

After 2.5 seconds (or on any user input - mouse click, key press), the
greeting fades out and the login card fades in.

#### Sub-layer 2b: Login card

- A large clock at the top center (thin font, 72px).
- The current date below the clock.
- A glass card in the center with:
  - A circular avatar (gradient-filled, with the user's first initial).
  - The username below the avatar.
  - A password TextField with a focus-glow border.
  - A session selector ComboBox.
  - Reboot and power-off icon buttons.
  - A "Sign in" button with a gradient background.
  - An error message area (red text, only visible on auth failure).
- A horizontal avatar strip at the bottom for switching users.

The card has:

- A `FastBlur` behind it that blurs a snapshot of the wallpaper at the card's
  position - this is the "frosted glass" effect.
- A semi-transparent dark fill (`#0E1422` with 55% opacity).
- A subtle 1px white border at 18% opacity.
- A drop-shadow for depth.

On authentication failure, the card shakes horizontally four times and the
password field is cleared.  On success, the card fades out and SDDM hands
control to the Plasma session.

#### Customising the SDDM theme

The theme reads its config from `theme.conf` in the same directory.  Key
settings:

```ini
[General]
color=#1A1F2E                      # Background fallback color
background=assets/wallpaper.mp4    # Video or image
background_type=video              # 'video' or 'image'
blur_strength=22                   # 0-50, higher = more blur
glass_color=#0E1422                # Card base color
glass_alpha=140                    # 0-255, card opacity
accent=#78A0FF                     # Accent color (buttons, focus)
clock_24h=true                     # 24-hour clock format
clock_font_size=72
greeting_text=Welcome to NovaOS
greeting_subtext=Hello. Just a moment...
```

### Layer 3 - Desktop

The desktop uses four overlapping theme systems:

#### 3a. Kvantum theme (Qt widget style)

Located at `archiso/novaos/airootfs/usr/share/Kvantum/NovaOS/`.  Provides:

- Translucent Qt buttons, menus, tooltips.
- Blur behind menus and tooltips (when `blurring=true`).
- Custom scrollbars, sliders, checkboxes.
- Gradient accents on focus.

The main config is in `NovaOS.kvconfig` (the human-editable settings) and
`NovaOS.svg` (the actual rendered assets - 9-slice scalable).  For a quick
color change, edit `NovaOS.kvconfig` and look for the `[Colors]` section:

```ini
[Colors]
window=#0E1422                # Window background
window_opacity=0.78
base=#16203A                  # View background (lists, text fields)
base_opacity=0.65
button=#1F2A47                # Button background
button_opacity=0.55
highlight=#78A0FF             # Selection / focus
highlight_opacity=0.55
text=#E8EEF7                  # Primary text
```

To change the accent color globally, replace every `#78A0FF` with your new
color.  Use `sed`:

```bash
ACCENT="#FF6B9D"  # example: pink
sed -i "s/#78A0FF/$ACCENT/g" archiso/novaos/airootfs/usr/share/Kvantum/NovaOS/NovaOS.kvconfig
sed -i "s/#78A0FF/$ACCENT/g" archiso/novaos/airootfs/usr/share/color-schemes/NovaOSCrystal.colors
sed -i "s/#78A0FF/$ACCENT/g" archiso/novaos/airootfs/usr/share/sddm/themes/novaos/theme.conf
```

#### 3b. Plasma Look-and-Feel package

Located at `archiso/novaos/airootfs/usr/share/plasma/look-and-feel/com.novaos.desktop/`.
This is what the user picks from System Settings -> Appearance -> Global Theme.
It bundles:

- `contents/defaults` - the default color scheme, icon theme, widget style,
  window decoration, KSplash and SDDM theme.
- `contents/splash/Splash.qml` - the boot splash.
- `contents/lockscreen/` - the lock screen (uses SDDM theme by default).
- `contents/logout/` - the logout screen.

To change the default wallpaper, edit `contents/defaults` and set:

```
[Desktop]
WallpaperPlugin=smart-video-wallpaper
Wallpaper=/usr/share/wallpapers/NovaOS/YourNewWallpaper.mp4
```

#### 3c. Color scheme

Located at `archiso/novaos/airootfs/usr/share/color-schemes/NovaOSCrystal.colors`.
This is a standard KDE color scheme file (INI format).  It defines colors for
every UI element (Window, Button, View, Selection, Tooltip, Complementary).

#### 3d. Icon theme

Located at `archiso/novaos/airootfs/usr/share/icons/NovaOS-Crystal/`.  Inherits
from `breeze-dark`, `papirus-dark`, `Tela-circle`, `Adwaita`, and `hicolor`
(in that order - the first match wins).

To add your own icons, drop them into the appropriate size directory:

- `16x16/apps/your-app.png`
- `22x22/apps/your-app.png`
- `32x32/apps/your-app.png`
- `48x48/apps/your-app.png`
- `64x64/apps/your-app.png`
- `128x128/apps/your-app.png`
- `scalable/apps/your-app.svg`

## Animated wallpapers

NovaOS uses the `smart-video-wallpaper-reborn` Plasma plugin to play `.mp4`
files as the desktop wallpaper.  The default wallpaper is
`/usr/share/wallpapers/NovaOS/CrystalAurora.mp4`.

To replace it:

1. Put your `.mp4` in `themes/wallpapers/`.
2. Edit `archiso/novaos/airootfs/usr/share/wallpapers/NovaOS/metadata.desktop`
   to point at it.
3. Edit `archiso/novaos/airootfs/usr/share/sddm/themes/novaos/theme.conf`
   `background=` to use the same file (for a consistent look across login
   and desktop).

The NovaOS resource-maximizer daemon will automatically pause the wallpaper
playback when a fullscreen game is detected, to free up GPU resources.

## Window decorations

NovaOS uses borderless windows with a 36-pixel titlebar.  The window
decoration is implemented as a KDecoration3 plugin (`org.kde.novaos`).
Source is at `themes/plasma-novaos/decoration/`.

Key behaviors:

- Active window has a 1px accent line at the top.
- Inactive windows have no accent line.
- Maximized windows are fully borderless.
- Titlebar buttons: close, minimize, maximize (in that order, on the right).

## Customising the boot animation

To change the KSplash animation, edit `Splash.qml`.  Common changes:

- **Background color:** Edit the `Rectangle` color in `root`.
- **Logo:** Replace `images/novaos-logo.svg`.
- **Particle count:** Edit the `Repeater` `model: 32` value.
- **Particle color:** Edit the `color: "#78A0FF"` in the Repeater.
- **Status text:** Edit the `text: "Hello. Just a moment..."`.
- **Animation duration:** Edit the `NumberAnimation` `duration:` values.

## Font choices

NovaOS uses **Inter** for everything UI-related, with **JetBrains Mono** for
monospace and **Noto Sans** for fallback.  To change the system font:

1. Edit `archiso/novaos/airootfs/etc/skel/.config/kdeglobals`.
2. Find the `[Fonts]` section.
3. Replace every `Inter` with your preferred font family.
4. Add the font to `packages.x86_64` (e.g. `ttf-your-font`).
5. Run `fc-cache -f` after install.

## Sound theme

NovaOS ships a minimal sound theme at `themes/sounds/`.  It provides
`login.ogg`, `logout.ogg`, `error.ogg`, and `notification.ogg`.  These are
wired into SDDM and Plasma notifications via the `theme.conf` settings.

To replace:

1. Drop your `.ogg` files in `themes/sounds/`.
2. Edit `archiso/novaos/airootfs/usr/share/sounds/NovaOS/index.theme` to
   list them.
3. Update `theme.conf` `sound_login=`, `sound_logout=`, `sound_error=` to
   match.

## Testing themes locally

To test a theme without rebuilding the ISO:

1. Copy the theme files into the appropriate system directory:
   ```bash
   sudo cp -r themes/sddm-novaos/* /usr/share/sddm/themes/novaos/
   sudo cp -r themes/kvantum-novaos/* /usr/share/Kvantum/NovaOS/
   ```
2. Apply the theme:
   ```bash
   sddm-greeter --test-mode --theme /usr/share/sddm/themes/novaos
   kvantummanager --set NovaOS
   lookandfeeltool --apply com.novaos.desktop
   ```
3. Log out and back in to see the changes.
