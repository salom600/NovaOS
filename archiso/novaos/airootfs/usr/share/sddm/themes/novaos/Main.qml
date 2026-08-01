// NovaOS SDDM Theme - Main.qml
// Layer 1: boot -> greeting "Hello. Just a moment..." + clock + animated wallpaper
// Layer 2: user selection + glass password card with blur + transitions
// Layer 3: handover to KDE Plasma 6 desktop

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Window
import Qt5Compat.GraphicalEffects
import SddmComponents 2.0

Rectangle {
    id: root
    color: config.color || "#1A1F2E"
    anchors.fill: parent

    property var config: {
        "background_type": "video",
        "background": "assets/wallpaper.mp4",
        "background_fill": "cover",
        "accent": "#78A0FF",
        "blur_strength": 22,
        "glass_color": "#0E1422",
        "glass_alpha": 140,
        "clock_24h": true,
        "clock_font_size": 72,
        "greeting_text": "Welcome to NovaOS",
        "greeting_subtext": "Hello. Just a moment..."
    }

    // ---------- Background (video / static) ----------
    Loader {
        id: backgroundLoader
        anchors.fill: parent
        sourceComponent: config.background_type === "video"
                         ? videoBg : imageBg
    }

    Component {
        id: videoBg
        Video {
            anchors.fill: parent
            source: config.background
            muted: true
            loops: MediaPlayer.Infinite
            fillMode: VideoOutput.PreserveAspectCrop
            playing: true
        }
    }

    Component {
        id: imageBg
        Image {
            anchors.fill: parent
            source: config.background
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: true
        }
    }

    // Dim gradient for readability
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: "#80081018" }
            GradientStop { position: 0.5; color: "#50081018" }
            GradientStop { position: 1.0; color: "#90081018" }
        }
    }

    // ---------- Layer 1: Greeting (auto-hides after 2.5s) ----------
    Item {
        id: layer1
        anchors.fill: parent
        opacity: 1.0
        visible: opacity > 0.01

        Behavior on opacity { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 24

            // Logo with glow
            Item {
                width: 140
                height: 140
                Layout.alignment: Qt.AlignHCenter
                Image {
                    id: logo
                    anchors.fill: parent
                    source: "assets/novaos-logo.svg"
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                }
                DropShadow {
                    anchors.fill: logo
                    source: logo
                    radius: 22
                    samples: 32
                    color: config.accent
                    opacity: 0.7
                    spread: 0.5
                }
                ScaleAnimator on scale {
                    from: 0.7; to: 1.0; duration: 800
                    easing.type: Easing.OutBack
                    running: true
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: config.greeting_text
                color: "#F4F7FF"
                font.family: "Inter"
                font.weight: Font.DemiBold
                font.pixelSize: 38
                renderType: Text.NativeRendering

                OpacityAnimator on opacity {
                    from: 0; to: 1; duration: 600
                    easing.type: Easing.OutCubic
                    running: true
                }
            }

            Text {
                id: subtext
                Layout.alignment: Qt.AlignHCenter
                text: config.greeting_subtext
                color: "#A6B4D2"
                font.family: "Inter"
                font.weight: Font.Light
                font.pixelSize: 20

                // blinking ellipsis
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    NumberAnimation { from: 0.35; to: 1.0; duration: 700 }
                    NumberAnimation { from: 1.0; to: 0.35; duration: 700 }
                }
            }
        }

        // Auto-advance to Layer 2 after 2.5s or on user interaction
        Timer {
            interval: 2500
            running: true
            repeat: false
            onTriggered: layer1.opacity = 0
        }
        MouseArea {
            anchors.fill: parent
            onClicked: layer1.opacity = 0
        }
    }

    // ---------- Layer 2: User + Password (glass card) ----------
    Item {
        id: layer2
        anchors.fill: parent
        opacity: 0.0
        visible: opacity > 0.01

        Behavior on opacity { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }

        onVisibleChanged: if (visible) opacity = 1.0

        // Big clock
        ColumnLayout {
            id: clockColumn
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 0.10 * parent.height
            spacing: 8

            Text {
                id: clockText
                Layout.alignment: Qt.AlignHCenter
                color: "#E8EEF7"
                font.family: "Inter"
                font.weight: Font.Thin
                font.pixelSize: config.clock_font_size || 72
                renderType: Text.NativeRendering

                Timer {
                    interval: 1000
                    running: layer2.visible
                    repeat: true
                    onTriggered: {
                        let now = new Date();
                        let hh = String(now.getHours()).padStart(2, "0");
                        let mm = String(now.getMinutes()).padStart(2, "0");
                        clockText.text = hh + ":" + mm;
                    }
                    Component.onCompleted: clockText.text = Qt.formatDateTime(new Date(), "hh:mm")
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                color: "#A0AEC8"
                font.family: "Inter"
                font.weight: Font.Light
                font.pixelSize: 18
                text: Qt.formatDateTime(new Date(), "dddd, MMMM d")
            }
        }

        // Glass login card
        Rectangle {
            id: glassCard
            width: 420
            height: 460
            radius: 24
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: 60
            color: Qt.rgba(
                parseInt(config.glass_color.substr(1,2), 16) / 255,
                parseInt(config.glass_color.substr(3,2), 16) / 255,
                parseInt(config.glass_color.substr(5,2), 16) / 255,
                (config.glass_alpha || 140) / 255
            )
            border.color: Qt.rgba(1, 1, 1, 0.18)
            border.width: 1

            // Blur background behind card
            FastBlur {
                anchors.fill: parent
                source: ShaderEffectSource {
                    sourceItem: backgroundLoader.item
                    sourceRect: Qt.rect(glassCard.x, glassCard.y, glassCard.width, glassCard.height)
                }
                radius: config.blur_strength
                transparentBorder: true
            }

            layer.enabled: true
            layer.effect: DropShadow {
                radius: 28
                samples: 40
                color: "#80000000"
                verticalOffset: 8
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 32
                spacing: 18

                // User avatar
                Item {
                    width: 88; height: 88
                    Layout.alignment: Qt.AlignHCenter

                    Rectangle {
                        id: avatar
                        anchors.fill: parent
                        radius: width / 2
                        gradient: Gradient {
                            orientation: Gradient.Vertical
                            GradientStop { position: 0.0; color: "#78A0FF" }
                            GradientStop { position: 1.0; color: "#4A6FE3" }
                        }
                        border.color: Qt.rgba(1,1,1,0.6)
                        border.width: 2

                        Text {
                            anchors.centerIn: parent
                            text: userNameText.text.charAt(0).toUpperCase() || "?"
                            color: "#FFFFFF"
                            font.family: "Inter"
                            font.weight: Font.Bold
                            font.pixelSize: 38
                        }
                    }
                    ScaleAnimator on scale {
                        from: 0.4; to: 1.0; duration: 500
                        easing.type: Easing.OutBack
                        running: layer2.visible
                    }
                }

                Text {
                    id: userNameText
                    Layout.alignment: Qt.AlignHCenter
                    color: "#F4F7FF"
                    font.family: "Inter"
                    font.weight: Font.Medium
                    font.pixelSize: 22
                    text: (userList.currentItem != null ? userList.currentItem.userName : "") || "novaos"
                }

                TextField {
                    id: passwordField
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    placeholderText: config.password_placeholder || "Enter password"
                    placeholderTextColor: "#A0AEC8"
                    echoMode: TextInput.Password
                    color: "#F4F7FF"
                    font.family: "Inter"
                    font.pixelSize: 16
                    horizontalAlignment: TextInput.AlignHCenter

                    background: Rectangle {
                        color: Qt.rgba(1, 1, 1, 0.06)
                        radius: 14
                        border.color: passwordField.activeFocus ? config.accent : Qt.rgba(1,1,1,0.12)
                        border.width: 1
                    }

                    Keys.onReturnPressed: {
                        sddm.login(userList.currentItem ? userList.currentItem.userName : "novaos",
                                   passwordField.text,
                                   sessionCombo.currentText);
                    }
                    Keys.onEnterPressed: {
                        sddm.login(userList.currentItem ? userList.currentItem.userName : "novaos",
                                   passwordField.text,
                                   sessionCombo.currentText);
                    }
                }

                // Session selector
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    ComboBox {
                        id: sessionCombo
                        Layout.fillWidth: true
                        Layout.preferredHeight: 42
                        model: sessionModel
                        textRole: "name"

                        background: Rectangle {
                            color: Qt.rgba(1, 1, 1, 0.06)
                            radius: 12
                            border.color: Qt.rgba(1,1,1,0.10)
                            border.width: 1
                        }
                    }

                    Button {
                        Layout.preferredWidth: 42
                        Layout.preferredHeight: 42
                        text: "⟲"
                        onClicked: sddm.reboot()

                        background: Rectangle {
                            color: Qt.rgba(1, 1, 1, 0.06)
                            radius: 12
                        }
                    }
                    Button {
                        Layout.preferredWidth: 42
                        Layout.preferredHeight: 42
                        text: "⏻"
                        onClicked: sddm.powerOff()

                        background: Rectangle {
                            color: Qt.rgba(255, 90, 110, 0.18)
                            radius: 12
                        }
                    }
                }

                // Login button
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    text: "Sign in"

                    contentItem: Text {
                        text: parent.text
                        color: "#FFFFFF"
                        font.family: "Inter"
                        font.weight: Font.Bold
                        font.pixelSize: 16
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        radius: 14
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: "#78A0FF" }
                            GradientStop { position: 1.0; color: "#4A6FE3" }
                        }
                        ScaleAnimator on scale {
                            from: 1.0; to: 1.02; duration: 120
                            easing.type: Easing.OutCubic
                            running: parent.parent.pressed
                        }
                    }

                    onClicked: {
                        sddm.login(userList.currentItem ? userList.currentItem.userName : "novaos",
                                   passwordField.text,
                                   sessionCombo.currentText);
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    color: "#FF6B6B"
                    text: errorMessage.text
                    font.family: "Inter"
                    font.pixelSize: 13
                    visible: text.length > 0
                }
            }

            Connections {
                target: sddm
                function onLoginFailed() {
                    shakeAnim.start();
                    passwordField.text = "";
                    errorMessage.text = "Authentication failed. Please try again.";
                }
                function onLoginSucceeded() {
                    errorMessage.text = "";
                    layer2.opacity = 0;
                }
            }

            SequentialAnimation {
                id: shakeAnim
                loops: 1
                NumberAnimation { target: glassCard; property: "x"; from: glassCard.x; to: glassCard.x - 12; duration: 50 }
                NumberAnimation { target: glassCard; property: "x"; from: glassCard.x - 12; to: glassCard.x + 12; duration: 50 }
                NumberAnimation { target: glassCard; property: "x"; from: glassCard.x + 12; to: glassCard.x - 6; duration: 50 }
                NumberAnimation { target: glassCard; property: "x"; from: glassCard.x - 6; to: glassCard.x; duration: 50 }
            }
        }

        // Bottom: user picker (avatars)
        ListView {
            id: userList
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 32
            width: Math.min(parent.width - 80, contentWidth)
            height: 80
            orientation: ListView.Horizontal
            spacing: 18
            clip: true
            model: userModel

            delegate: Item {
                width: 70
                height: 70
                property string userName: model.userName

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: Qt.rgba(1,1,1,0.06)
                    border.color: ListView.isCurrentItem ? config.accent : Qt.rgba(1,1,1,0.2)
                    border.width: 2

                    Text {
                        anchors.centerIn: parent
                        text: model.userName.charAt(0).toUpperCase()
                        color: "#FFFFFF"
                        font.family: "Inter"
                        font.pixelSize: 24
                        font.weight: Font.Bold
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: userList.currentIndex = index
                    }
                }
            }
        }
    }

    // Boot-time entry animation
    Component.onCompleted: {
        // Wait one frame then start layer 2 hidden
        layer2.opacity = 0;
    }
}
