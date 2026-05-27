import QtQuick
import QtQuick.Controls.Basic
import "components"

Rectangle {
    id: statusBar
    property string lineId: ""
    property string systemStatus: "stopped"
    property int okCount: 0
    property int ngCount: 0
    property real tactRate: 0.0

    height: 40
    color: Theme.bgSecondary

    Row {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 20

        Rectangle {
            width: 12; height: 12; radius: 6
            anchors.verticalCenter: parent.verticalCenter
            color: {
                switch (systemStatus) {
                    case "running": return Theme.statusOK;
                    case "paused": return Theme.statusWarning;
                    default: return Theme.textMuted;
                }
            }
        }

        Text {
            text: systemStatus === "running" ? qsTr("运行中") :
                  systemStatus === "paused" ? qsTr("已暂停") : qsTr("已停止")
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeSM
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: qsTr("产线 ") + lineId
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSM
            anchors.verticalCenter: parent.verticalCenter
        }

        Item { width: 20 }

        Text {
            text: qsTr("节拍: ") + tactRate.toFixed(1) + qsTr("/min")
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSM
            anchors.verticalCenter: parent.verticalCenter
        }

        Item { width: 20 }

        Text {
            text: qsTr("OK: ") + okCount
            color: Theme.statusOK
            font.pixelSize: Theme.fontSizeMD
            font.bold: true
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: qsTr("NG: ") + ngCount
            color: ngCount > 0 ? Theme.statusNG : Theme.textSecondary
            font.pixelSize: Theme.fontSizeMD
            font.bold: true
            anchors.verticalCenter: parent.verticalCenter
        }

        Item { Layout.fillWidth: true }

        ActionButton {
            anchors.verticalCenter: parent.verticalCenter
            implicitHeight: 32
            buttonText: qsTr("⚙ 设置")
            bgColor: Theme.bgTertiary
        }

        ActionButton {
            anchors.verticalCenter: parent.verticalCenter
            implicitHeight: 32
            buttonText: qsTr("📋 日志")
            bgColor: Theme.bgTertiary
        }
    }
}
