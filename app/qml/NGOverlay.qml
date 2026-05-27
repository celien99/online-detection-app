import QtQuick
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
    color: Qt.rgba(0, 0, 0, 0.92)
    z: 100

    Timer {
        id: countdownTimer
        interval: 1000
        repeat: true
        running: overlay.visible
        onTriggered: {
            if (countdown > 0) countdown--;
        }
    }

    Column {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 16

            Rectangle {
                color: Theme.statusNG
                radius: 4
                height: 40
                width: warningText.implicitWidth + 32
                Text {
                    id: warningText
                    anchors.centerIn: parent
                    text: qsTr("⚠ DEFECT DETECTED")
                    color: "#ffffff"
                    font.pixelSize: Theme.fontSizeLG
                    font.bold: true
                }
            }
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width * 0.85
            height: parent.height * 0.5
            spacing: 12

            Rectangle {
                width: parent.width / 2 - 6
                height: parent.height
                color: Theme.bgCard
                border { width: 1; color: "#333" }

                Column {
                    anchors.fill: parent
                    Text {
                        text: qsTr("📷 ") + cameraId + qsTr(" · 原始图像")
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeXS
                        padding: 6
                    }
                    Image {
                        width: parent.width
                        height: parent.height - 28
                        source: "image://camera/" + cameraId + "_original"
                        fillMode: Image.PreserveAspectFit
                        cache: false
                    }
                }
            }

            Rectangle {
                width: parent.width / 2 - 6
                height: parent.height
                color: Theme.bgCard
                border { width: 1; color: "#333" }

                Column {
                    anchors.fill: parent
                    Text {
                        text: qsTr("🔥 异常热力图 · Score: ") + confidence.toFixed(2)
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeXS
                        padding: 6
                    }
                    Image {
                        width: parent.width
                        height: parent.height - 28
                        source: "image://camera/" + cameraId + "_heatmap"
                        fillMode: Image.PreserveAspectFit
                        cache: false
                    }
                }
            }
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8

            InfoCard {
                accentColor: Theme.statusNG
                cardLabel: qsTr("缺陷类型")
                cardValue: defectType
            }
            InfoCard {
                accentColor: Theme.statusWarning
                cardLabel: qsTr("置信度")
                cardValue: confidence.toFixed(2)
            }
            InfoCard {
                accentColor: Theme.accent
                cardLabel: qsTr("相机")
                cardValue: cameraId
            }
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 16

            ActionButton {
                buttonText: qsTr("❌ 确认缺陷 (NG)")
                bgColor: Theme.statusNG
                implicitHeight: 56
                implicitWidth: 220
                font.pixelSize: Theme.fontSizeMD
                onClicked: overlay.confirmNG()
            }
            ActionButton {
                buttonText: qsTr("🔍 标记需复核")
                bgColor: Theme.statusWarning
                textColor: "#000000"
                implicitHeight: 56
                implicitWidth: 220
                font.pixelSize: Theme.fontSizeMD
                onClicked: overlay.markReview()
            }
            ActionButton {
                buttonText: qsTr("✓ 误报放行 (OK)")
                bgColor: "#444444"
                implicitHeight: 56
                implicitWidth: 220
                font.pixelSize: Theme.fontSizeMD
                onClicked: overlay.dismissFalseAlarm()
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: qsTr("自动确认倒计时 ") + countdown + qsTr("s · 超时默认按 NG 处理")
            color: Theme.textMuted
            font.pixelSize: Theme.fontSizeXS
        }
    }
}
