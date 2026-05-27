import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import styles

/*
  Industrial-grade modal dialog -- dark glass, backdrop overlay,
  subtle shadow, animated entrance, large touch-friendly buttons.
  Usage:

    IndustrialDialog {
        id: myDialog
        title: "新增记录"
        contentHeight: 200
        onAccepted: { ... handle confirm ... }
        // Content goes inside:
        contentItem: ColumnLayout { ... }
    }
*/
Popup {
    id: root

    modal: true
    closePolicy: Popup.CloseOnEscape
    anchors.centerIn: Overlay.overlay
    padding: 0

    // ── Public API ──
    property string title: ""
    property real dialogContentHeight: 160
    property string acceptText: qsTr("确认")
    property string cancelText: qsTr("取消")
    property bool showCancel: true
    property alias dialogContent: contentLoader.sourceComponent

    signal accepted()
    signal rejected()

    // ── Backdrop overlay ──
    parent: Overlay.overlay

    Rectangle {
        id: backdrop
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.55)
        z: root.z - 1
    }

    // ── Enter animation ──
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.animNormal; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.96; to: 1.0; duration: Theme.animNormal; easing.type: Easing.OutCubic }
        }
    }

    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.animFast }
    }

    // ── Dialog body ──
    background: Rectangle {
        id: dialogBody
        width: 440
        implicitWidth: 440
        implicitHeight: 52 + 1 + root.dialogContentHeight + Theme.spacingLG * 2 + 1 + 56
        color: Theme.bgSecondary
        radius: Theme.radiusLG
        border { width: 1; color: Qt.rgba(1, 1, 1, 0.12) }

        // Subtle top accent line
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 2
            radius: Theme.radiusLG
            color: Theme.accent
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.bgSecondary
            }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── Header ──
            Rectangle {
                id: headerRow
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                color: "transparent"

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: Theme.spacingLG
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.title
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMD
                    font.weight: Font.DemiBold
                }
            }

            // ── Separator ──
            Rectangle {
                id: separator
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Qt.rgba(1, 1, 1, 0.06)
            }

            // ── Content area ──
            Item {
                id: contentArea
                Layout.fillWidth: true
                Layout.preferredHeight: root.dialogContentHeight
                Layout.leftMargin: Theme.spacingLG
                Layout.rightMargin: Theme.spacingLG
                Layout.topMargin: Theme.spacingLG
                Layout.bottomMargin: Theme.spacingLG

                Loader {
                    id: contentLoader
                    anchors.fill: parent
                }
            }

            // ── Separator ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Qt.rgba(1, 1, 1, 0.06)
            }

            // ── Footer (buttons) ──
            Rectangle {
                id: footerRow
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                color: "transparent"

                RowLayout {
                    anchors.right: parent.right
                    anchors.rightMargin: Theme.spacingMD
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.spacingSM

                    // Cancel button
                    Rectangle {
                        visible: root.showCancel
                        Layout.preferredWidth: 88
                        Layout.preferredHeight: 40
                        radius: Theme.radiusSM
                        color: cancelMouse.containsMouse
                               ? Qt.rgba(1, 1, 1, 0.08)
                               : "transparent"
                        border { width: 1; color: Qt.rgba(1, 1, 1, 0.12) }

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
                            onClicked: {
                                root.rejected();
                                root.close();
                            }
                        }
                    }

                    // Accept button
                    Rectangle {
                        Layout.preferredWidth: 88
                        Layout.preferredHeight: 40
                        radius: Theme.radiusSM
                        color: acceptMouse.containsMouse
                               ? Theme.accentGreen
                               : Theme.accentGreenDim
                        border { width: 1; color: acceptMouse.containsMouse
                                         ? Theme.accentGreen
                                         : Theme.accentGreen }

                        Behavior on color { ColorAnimation { duration: Theme.animFast } }

                        Text {
                            anchors.centerIn: parent
                            text: root.acceptText
                            color: acceptMouse.containsMouse ? "#000000" : Theme.accentGreen
                            font.pixelSize: Theme.fontSizeSM
                            font.weight: Font.DemiBold
                        }

                        MouseArea {
                            id: acceptMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.accepted();
                                root.close();
                            }
                        }
                    }
                }
            }
        }
    }
}
