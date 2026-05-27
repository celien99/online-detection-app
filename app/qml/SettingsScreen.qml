import QtQuick
import QtQuick.Controls.Basic
import "components"

Rectangle {
    id: settingsScreen
    color: Theme.bgPrimary

    Row {
        anchors.fill: parent

        Rectangle {
            width: 180
            height: parent.height
            color: Theme.bgSecondary

            ListView {
                anchors.fill: parent
                model: [qsTr("📷 相机配置"), qsTr("🧠 检测模型"), qsTr("🔌 PLC 通讯"), qsTr("☁️ 离线平台"), qsTr("🔔 告警设置"), qsTr("💾 存储管理"), qsTr("ℹ️ 关于")]
                delegate: Rectangle {
                    width: 180
                    height: 40
                    color: model.index === 0 ? Theme.bgTertiary : "transparent"
                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSM
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: parent.height
            color: Theme.bgPrimary
            padding: 16

            Column { spacing: 10
                Text {
                    text: qsTr("📷 相机配置")
                    color: Theme.accent
                    font.pixelSize: Theme.fontSizeMD
                    font.bold: true
                }
                Text {
                    text: qsTr("相机列表和参数配置将在此处显示")
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSizeSM
                }
            }
        }
    }
}
