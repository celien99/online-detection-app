import QtQuick
import QtQuick.Controls.Basic
import "components"

Rectangle {
    id: logScreen
    color: Theme.bgPrimary

    property var logModel: []

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        Row {
            spacing: 12
            Text {
                text: qsTr("📋 检测日志")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
            Item { Layout.fillWidth: true }
            ActionButton {
                buttonText: qsTr("📥 导出 CSV")
                bgColor: Theme.bgTertiary
                implicitHeight: 36
            }
        }

        Row { spacing: 8
            Text { text: qsTr("筛选:"); color: Theme.textSecondary; anchors.verticalCenter: parent.verticalCenter }
            ComboBox {
                model: [qsTr("全部状态"), "OK", "NG", "REJECT"]
            }
            ComboBox {
                model: [qsTr("全部相机"), "CAM_FRONT", "CAM_RIGHT", "CAM_LEFT", "CAM_REAR"]
            }
        }

        ListView {
            id: logList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: logScreen.logModel
            clip: true

            header: Row {
                spacing: 4
                Repeater {
                    model: [qsTr("时间"), qsTr("相机"), qsTr("状态"), qsTr("缺陷类型"), qsTr("置信度"), qsTr("操作员")]
                    delegate: Rectangle {
                        width: logList.width / 6
                        height: 24
                        color: Theme.bgTertiary
                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }
                }
            }

            delegate: Row {
                spacing: 4
                Repeater {
                    model: [modelData.timestamp, modelData.camera_id, modelData.status, modelData.defect_type, modelData.confidence, modelData.operator_action]
                    delegate: Rectangle {
                        width: logList.width / 6
                        height: 28
                        color: index % 2 === 0 ? Theme.bgPrimary : Theme.bgSecondary
                        border { width: modelData.status === "NG" ? 1 : 0; color: Theme.statusNG }

                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            color: modelData.status === "NG" ? Theme.statusNG :
                                   modelData.status === "OK*" ? Theme.accent : Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }
                }
            }
        }
    }
}
