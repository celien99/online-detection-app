import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"
import styles

Rectangle {
    id: statusBar
    property string lineId: ""
    property string systemStatus: "stopped"
    property int okCount: 0
    property int ngCount: 0
    property real tactRate: 0.0

    height: 40
    color: Theme.bgSecondary

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 12

        Rectangle {
            width: 12; height: 12; radius: 6
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
        }

        Text {
            text: qsTr("产线 ") + lineId
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSM
        }

        Text {
            text: qsTr("节拍: ") + tactRate.toFixed(1) + qsTr("/min")
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSM
        }

        Text {
            text: qsTr("OK: ") + okCount
            color: Theme.statusOK
            font.pixelSize: Theme.fontSizeMD
            font.bold: true
        }

        Text {
            text: qsTr("NG: ") + ngCount
            color: ngCount > 0 ? Theme.statusNG : Theme.textSecondary
            font.pixelSize: Theme.fontSizeMD
            font.bold: true
        }

        Item { Layout.fillWidth: true }

        ActionButton {
            implicitHeight: 32
            buttonText: qsTr("⚙ 设置")
            bgColor: Theme.bgTertiary
        }

        ActionButton {
            implicitHeight: 32
            buttonText: qsTr("📋 日志")
            bgColor: Theme.bgTertiary
        }
    }
}
