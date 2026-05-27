import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"
import styles

Rectangle {
    id: overlay
    property string defectType: ""
    property real confidence: 0.0
    property string cameraId: ""
    property int countdown: 30

    signal confirmNG()
    signal markReview()
    signal dismissFalseAlarm()

    anchors.fill: parent
    color: Theme.bgOverlay
    z: 100

    Timer {
        id: countdownTimer
        interval: 1000
        repeat: true
        running: overlay.visible
        onTriggered: { if (countdown > 0) countdown--; }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingXL
        spacing: Theme.spacingLG

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMD

            Rectangle {
                Layout.preferredWidth: bannerText.implicitWidth + 40
                Layout.preferredHeight: 48
                radius: Theme.radiusMD
                color: Theme.statusNG
                Text {
                    id: bannerText
                    anchors.centerIn: parent
                    text: qsTr("DEFECT DETECTED")
                    color: "#ffffff"
                    font.pixelSize: Theme.fontSizeLG
                    font.bold: true
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredHeight: 48
                Layout.preferredWidth: countdownLabel.implicitWidth + 32
                radius: Theme.radiusMD
                color: countdown <= 5 ? Theme.statusNGDim : Theme.bgTertiary
                border {
                    width: 1
                    color: countdown <= 5 ? Theme.statusNG : Theme.borderStrong
                }
                Text {
                    id: countdownLabel
                    anchors.centerIn: parent
                    text: qsTr("Auto-confirm in ") + countdown + "s"
                    color: countdown <= 5 ? Theme.statusNG : Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSM
                    font.bold: true
                }
            }
        }

        // ── Body: images side by side ──
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacingMD

            // Original image
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Theme.bgCard
                radius: Theme.radiusMD
                border { width: 1; color: Theme.borderDefault }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 32
                        color: Theme.bgTertiary
                        radius: Theme.radiusMD
                        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: parent.radius; color: parent.color }
                        Text {
                            anchors.centerIn: parent
                            text: qsTr("Original  ") + cameraId
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }
                    Image {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.margins: 4
                        source: "image://camera/" + cameraId + "_original"
                        fillMode: Image.PreserveAspectFit
                        cache: false
                    }
                }
            }

            // Heatmap
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Theme.bgCard
                radius: Theme.radiusMD
                border { width: 1; color: Theme.borderDefault }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 32
                        color: Theme.bgTertiary
                        radius: Theme.radiusMD
                        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: parent.radius; color: parent.color }
                        Text {
                            anchors.centerIn: parent
                            text: qsTr("Heatmap  Score: ") + confidence.toFixed(4)
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }
                    Image {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.margins: 4
                        source: "image://camera/" + cameraId + "_heatmap"
                        fillMode: Image.PreserveAspectFit
                        cache: false
                    }
                }
            }
        }

        // ── Info cards ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMD

            InfoCard {
                accentColor: Theme.statusNG
                cardLabel: qsTr("Defect Type")
                cardValue: defectType || "--"
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.statusWarning
                cardLabel: qsTr("Confidence")
                cardValue: confidence.toFixed(3)
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.accent
                cardLabel: qsTr("Camera")
                cardValue: cameraId
                Layout.fillWidth: true
            }
            InfoCard {
                accentColor: Theme.textSecondary
                cardLabel: qsTr("Auto Action")
                cardValue: "NG"
                cardSubtext: qsTr("on timeout")
                Layout.fillWidth: true
            }
        }

        // ── Action buttons ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingLG

            ActionButton {
                buttonText: qsTr("Confirm NG")
                bgColor: Theme.statusNG
                Layout.fillWidth: true
                implicitHeight: Theme.touchComfort
                font { pixelSize: Theme.fontSizeMD; bold: true }
                onClicked: overlay.confirmNG()
            }
            ActionButton {
                buttonText: qsTr("Mark for Review")
                bgColor: Theme.statusWarning
                textColor: "#000000"
                Layout.fillWidth: true
                implicitHeight: Theme.touchComfort
                font { pixelSize: Theme.fontSizeMD; bold: true }
                onClicked: overlay.markReview()
            }
            ActionButton {
                buttonText: qsTr("Dismiss (False Alarm)")
                bgColor: Theme.bgTertiary
                Layout.fillWidth: true
                implicitHeight: Theme.touchComfort
                font { pixelSize: Theme.fontSizeMD; bold: true }
                onClicked: overlay.dismissFalseAlarm()
            }
        }
    }
}
