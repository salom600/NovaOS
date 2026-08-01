// NovaOS KSplash - "Crystal Glass" boot animation
// Animated: blue nebula morphing into the NovaOS mark + "Just a moment..."
// Hooks into Plasma's KSplashQML engine.

import QtQuick
import Qt5Compat.GraphicalEffects

Rectangle {
    id: root
    color: "#060810"
    anchors.fill: parent

    // Animated gradient background (shader-less, 2 stacked rectangles)
    Rectangle {
        id: nebula1
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: "#0A0E1C" }
            GradientStop { position: 0.5; color: "#0E1422" }
            GradientStop { position: 1.0; color: "#060810" }
        }

        Behavior on opacity { NumberAnimation { duration: 800; easing.type: Easing.InOutCubic } }
    }

    Rectangle {
        id: nebula2
        anchors.fill: parent
        opacity: 0.4
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "#08091A" }
            GradientStop { position: 0.5; color: "#101830" }
            GradientStop { position: 1.0; color: "#08091A" }
        }

        RotationAnimator on rotation {
            from: 0; to: 360
            duration: 18000
            loops: Animation.Infinite
            running: true
        }
    }

    // Floating particles
    Repeater {
        model: 32
        Rectangle {
            property real startX: Math.random() * root.width
            property real startY: Math.random() * root.height
            x: startX
            y: startY + Math.sin((Date.now() / 1000) + index) * 12
            width: 2 + Math.random() * 3
            height: width
            radius: width / 2
            color: "#78A0FF"
            opacity: 0.3 + Math.random() * 0.4
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                NumberAnimation { from: 0.2; to: 0.9; duration: 1500 + Math.random() * 2000 }
                NumberAnimation { from: 0.9; to: 0.2; duration: 1500 + Math.random() * 2000 }
            }
            YAnimator on y {
                from: startY; to: startY - 40 - Math.random() * 60
                duration: 3000 + Math.random() * 4000
                loops: Animation.Infinite
            }
        }
    }

    // Center: NovaOS logo (SVG)
    Image {
        id: logo
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -40
        width: 140
        height: 140
        source: "images/novaos-logo.svg"
        fillMode: Image.PreserveAspectFit
        smooth: true

        ScaleAnimator on scale {
            from: 0.6; to: 1.0
            duration: 800
            easing.type: Easing.OutBack
            running: true
        }
        OpacityAnimator on opacity {
            from: 0.0; to: 1.0
            duration: 600
            easing.type: Easing.OutCubic
            running: true
        }

        DropShadow {
            anchors.fill: logo
            source: logo
            radius: 22
            samples: 32
            color: "#78A0FF"
            opacity: 0.7
            spread: 0.5
            ScaleAnimator on scale {
                from: 0.8; to: 1.1; duration: 1200
                loops: Animation.Infinite
                running: true
                easing.type: Easing.InOutSine
            }
        }
    }

    // Progress bar (KDM/Plasma provides the value via 'progress' property)
    Item {
        id: progressBar
        width: 220
        height: 4
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: logo.bottom
        anchors.topMargin: 36

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(1, 1, 1, 0.08)
            radius: 2
        }

        Rectangle {
            width: parent.width * (typeof progress !== "undefined" ? progress / 100 : 0.0)
            height: parent.height
            color: "#78A0FF"
            radius: 2

            Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
        }
    }

    Text {
        id: status
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: progressBar.bottom
        anchors.topMargin: 18
        color: "#A0AEC8"
        text: "Hello. Just a moment..."
        font.family: "Inter"
        font.weight: Font.Light
        font.pixelSize: 16

        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { from: 0.35; to: 1.0; duration: 800 }
            NumberAnimation { from: 1.0; to: 0.35; duration: 800 }
        }
    }

    Text {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 36
        anchors.horizontalCenter: parent.horizontalCenter
        color: "#5C6A88"
        text: "NovaOS 2026.1  -  Crystal Glass"
        font.family: "Inter"
        font.weight: Font.Light
        font.pixelSize: 12
        opacity: 0.7
    }
}
