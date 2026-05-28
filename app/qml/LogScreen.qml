import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"
import styles

Rectangle {
    id: logScreen
    color: Theme.bgPrimary

    property var logModel: []
    property var viewModel: null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        // Header row
        RowLayout {
            Text {
                text: qsTr("检测日志")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
                Layout.fillWidth: true
            }

            ActionButton {
                buttonText: qsTr("导出 CSV")
                bgColor: Theme.bgTertiary
                implicitHeight: 36
                implicitWidth: 120
                onClicked: {
                    if (logScreen.viewModel) logScreen.viewModel.exportCSV("");
                }
            }
        }

        // Filters
        RowLayout {
            spacing: Theme.spacingSM
            Text { text: qsTr("筛选:"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
            ComboBox {
                id: statusFilter
                model: [qsTr("全部"), "OK", "NG", "REJECT"]
                implicitWidth: 120
                implicitHeight: 32
                background: Rectangle {
                    color: Theme.bgTertiary
                    radius: Theme.radiusSM
                    border { width: 1; color: Theme.borderStrong }
                }
                contentItem: Text {
                    text: statusFilter.currentText
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: Theme.spacingSM
                }
                onActivated: {
                    var val = currentText === qsTr("全部") ? "" : currentText;
                    if (logScreen.viewModel) logScreen.viewModel.setStatusFilter(val);
                }
            }
            ComboBox {
                id: cameraFilter
                model: [qsTr("全部相机"), "CAM_FRONT", "CAM_RIGHT", "CAM_LEFT", "CAM_REAR"]
                implicitWidth: 140
                implicitHeight: 32
                background: Rectangle {
                    color: Theme.bgTertiary
                    radius: Theme.radiusSM
                    border { width: 1; color: Theme.borderStrong }
                }
                contentItem: Text {
                    text: cameraFilter.currentText
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: Theme.spacingSM
                }
                onActivated: {
                    var val = currentText === qsTr("全部相机") ? "" : currentText;
                    if (logScreen.viewModel) logScreen.viewModel.setCameraFilter(val);
                }
            }
        }

        // Log table
        ListView {
            id: logList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: logScreen.logModel
            clip: true

            // Table header
            header: Rectangle {
                width: logList.width
                height: 32
                color: Theme.bgTertiary
                radius: Theme.radiusSM
                Row {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingSM
                    anchors.rightMargin: Theme.spacingSM
                    spacing: 4
                    Repeater {
                        model: [qsTr("时间"), qsTr("Camera"), qsTr("状态"), qsTr("缺陷"), qsTr("置信度"), qsTr("操作")]
                        delegate: Rectangle {
                            width: logList.width / 6
                            height: 32
                            color: "transparent"
                            Text {
                                anchors.centerIn: parent
                                text: modelData
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                                font.bold: true
                            }
                        }
                    }
                }
            }

            // Row delegate
            delegate: Rectangle {
                width: logList.width
                height: 32
                color: index % 2 === 0 ? Theme.bgPrimary : Theme.bgSecondary
                border {
                    width: modelData.status === "NG" ? 1 : 0
                    color: Theme.borderStrong
                }

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingSM
                    anchors.rightMargin: Theme.spacingSM
                    spacing: 4

                    Rectangle { width: logList.width / 6; height: 32; color: "transparent"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.timestamp ? new Date(modelData.timestamp * 1000).toLocaleTimeString(Qt.locale()) : ""
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }
                    Rectangle { width: logList.width / 6; height: 32; color: "transparent"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.camera_id || ""
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }
                    Rectangle { width: logList.width / 6; height: 32; color: "transparent"
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: statusLabel.implicitWidth + 10; height: 20; radius: Theme.radiusSM
                            color: modelData.status === "NG" ? Theme.statusNGDim :
                                   modelData.status === "OK" ? Theme.statusOKDim : Theme.statusRejectDim
                            Text {
                                id: statusLabel
                                anchors.centerIn: parent
                                text: modelData.status || ""
                                color: modelData.status === "NG" ? Theme.statusNG :
                                       modelData.status === "OK" ? Theme.statusOK : Theme.statusReject
                                font.pixelSize: Theme.fontSizeXS
                                font.bold: true
                            }
                        }
                    }
                    Rectangle { width: logList.width / 6; height: 32; color: "transparent"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.defect_type || "--"
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }
                    Rectangle { width: logList.width / 6; height: 32; color: "transparent"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.confidence ? modelData.confidence.toFixed(3) : "--"
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }
                    Rectangle { width: logList.width / 6; height: 32; color: "transparent"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.operator_action || "--"
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }
                }
            }
        }
    }
}
