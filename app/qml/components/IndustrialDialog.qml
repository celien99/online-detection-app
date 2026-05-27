import QtQuick
import QtQuick.Layouts
import styles

Rectangle {
    id: root

    anchors.fill: parent
    color: Qt.rgba(0, 0, 0, 0.58)
    visible: false
    z: 998

    property string title: ""
    property alias dialogContentHeight: contentSlot.implicitHeight
    property string acceptText: qsTr("确认")
    property string cancelText: qsTr("取消")
    property bool showCancel: true
    default property alias dialogContent: contentSlot.data

    signal accepted()
    signal rejected()

    function open() {
        root.visible = true;
        fadeIn.start();
    }
    function close() {
        fadeOut.start();
    }

    // Prevent clicks through to background
    MouseArea {
        anchors.fill: parent
        enabled: root.visible
        onClicked: { /* block clicks */ }
    }

    OpacityAnimator {
        id: fadeIn
        target: root
        from: 0; to: 1
        duration: Theme.animNormal
        easing.type: Easing.OutCubic
        onStopped: root.opacity = 1
    }
    OpacityAnimator {
        id: fadeOut
        target: root
        from: 1; to: 0
        duration: Theme.animFast
        onStopped: { root.visible = false; root.opacity = 1; }
    }

    // ── Shadow layer ──
    Rectangle {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 2
        width: card.width + 16
        height: card.height + 16
        radius: Theme.radiusLG + 4
        color: Qt.rgba(0, 0, 0, 0.3)
        opacity: root.opacity
    }

    // ── Card ──
    Rectangle {
        id: card
        width: 440
        anchors.centerIn: parent
        radius: Theme.radiusLG
        color: "#1a1e26"
        border { width: 1; color: Qt.rgba(1, 1, 1, 0.1) }

        // Card inner gradient overlay
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.03) }
                GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.02) }
            }
        }

        // Top accent bar
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 3
            radius: Theme.radiusLG
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.accent }
                GradientStop { position: 1.0; color: Qt.rgba(0.345, 0.651, 1, 0.5) }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.topMargin: 3
            spacing: 0

            // ── Header ──
            Item {
                id: headerRow
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                Layout.leftMargin: Theme.spacingLG
                Layout.rightMargin: Theme.spacingLG

                Text {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.title
                    color: Theme.textPrimary
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                }
            }

            Rectangle {
                id: sep1
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                Layout.leftMargin: Theme.spacingLG
                Layout.rightMargin: Theme.spacingLG
                color: Qt.rgba(1, 1, 1, 0.05)
            }

            // ── Content ──
            Item {
                id: contentSlot
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(implicitHeight, 80)
                Layout.leftMargin: Theme.spacingLG
                Layout.rightMargin: Theme.spacingLG
                Layout.topMargin: Theme.spacingMD
                Layout.bottomMargin: Theme.spacingMD
            }

            Rectangle {
                id: sep2
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                Layout.leftMargin: Theme.spacingLG
                Layout.rightMargin: Theme.spacingLG
                color: Qt.rgba(1, 1, 1, 0.05)
            }

            // ── Footer ──
            Item {
                id: footerRow
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                Layout.leftMargin: Theme.spacingLG
                Layout.rightMargin: Theme.spacingMD

                RowLayout {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 10

                    // Cancel
                    Rectangle {
                        visible: root.showCancel
                        implicitWidth: 90
                        implicitHeight: 36
                        radius: 4
                        color: cancelMouse.containsMouse
                               ? Qt.rgba(1, 1, 1, 0.06)
                               : "transparent"
                        border { width: 1; color: Qt.rgba(1, 1, 1, 0.15) }

                        Behavior on color { ColorAnimation { duration: Theme.animFast } }

                        Text {
                            anchors.centerIn: parent
                            text: root.cancelText
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeSM
                        }

                        MouseArea {
                            id: cancelMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { root.rejected(); root.close(); }
                        }
                    }

                    // Accept
                    Rectangle {
                        implicitWidth: 90
                        implicitHeight: 36
                        radius: 4
                        color: acceptMouse.containsMouse
                               ? "#4169e1"
                               : Theme.accent
                        border { width: 1; color: acceptMouse.containsMouse
                                         ? "#4169e1"
                                         : Theme.accent }

                        Behavior on color { ColorAnimation { duration: Theme.animFast } }

                        Text {
                            anchors.centerIn: parent
                            text: root.acceptText
                            color: "#ffffff"
                            font.pixelSize: Theme.fontSizeSM
                            font.weight: Font.DemiBold
                        }

                        MouseArea {
                            id: acceptMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { root.accepted(); root.close(); }
                        }
                    }
                }
            }
        }
    }
}
