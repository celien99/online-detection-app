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
    property var tableColumns: [
        { title: qsTr("时间"), weight: 1.15 },
        { title: qsTr("Camera"), weight: 1.05 },
        { title: qsTr("状态"), weight: 0.65 },
        { title: qsTr("缺陷"), weight: 1.25 },
        { title: qsTr("置信度"), weight: 0.7 },
        { title: qsTr("操作"), weight: 0.95 }
    ]

    function tableColumnWidth(weight) {
        var totalWeight = 0
        for (var i = 0; i < tableColumns.length; i++) {
            totalWeight += tableColumns[i].weight
        }
        var available = Math.max(0, logList.width - Theme.spacingSM * 2 - 4 * (tableColumns.length - 1))
        return Math.floor(available * weight / totalWeight)
    }

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

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Log table
            ListView {
                id: logList
                anchors.fill: parent
                model: logScreen.logModel
                clip: true
                visible: count > 0

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
                            model: logScreen.tableColumns
                            delegate: Rectangle {
                                width: logScreen.tableColumnWidth(modelData.weight)
                                height: 32
                                color: "transparent"
                                Text {
                                    anchors.centerIn: parent
                                    width: parent.width - 4
                                    text: modelData.title
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeXS
                                    font.bold: true
                                    horizontalAlignment: Text.AlignHCenter
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                // Row delegate
                delegate: Rectangle {
                    width: logList.width
                    height: 36
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

                        Rectangle { width: logScreen.tableColumnWidth(logScreen.tableColumns[0].weight); height: parent.height; color: "transparent"
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 4
                                text: modelData.timestamp ? new Date(modelData.timestamp * 1000).toLocaleTimeString(Qt.locale()) : ""
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                                elide: Text.ElideRight
                            }
                        }
                        Rectangle { width: logScreen.tableColumnWidth(logScreen.tableColumns[1].weight); height: parent.height; color: "transparent"
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 4
                                text: modelData.camera_id || ""
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                                elide: Text.ElideRight
                            }
                        }
                        Rectangle { width: logScreen.tableColumnWidth(logScreen.tableColumns[2].weight); height: parent.height; color: "transparent"
                            StatusBadge {
                                anchors.verticalCenter: parent.verticalCenter
                                badgeText: modelData.status || "--"
                                badgeStatus: modelData.status === "NG" ? "ng" : (modelData.status === "OK" ? "ok" : "warning")
                                maxBadgeWidth: parent.width
                            }
                        }
                        Rectangle { width: logScreen.tableColumnWidth(logScreen.tableColumns[3].weight); height: parent.height; color: "transparent"
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 4
                                text: modelData.defect_type || "--"
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                                elide: Text.ElideRight
                            }
                        }
                        Rectangle { width: logScreen.tableColumnWidth(logScreen.tableColumns[4].weight); height: parent.height; color: "transparent"
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 4
                                text: modelData.confidence ? modelData.confidence.toFixed(3) : "--"
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                        Rectangle { width: logScreen.tableColumnWidth(logScreen.tableColumns[5].weight); height: parent.height; color: "transparent"
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 4
                                text: modelData.operator_action || "--"
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }

            EmptyState {
                anchors.fill: parent
                visible: logList.count === 0
                title: qsTr("暂无检测日志")
                message: qsTr("检测记录会在相机完成一次推理后写入本地日志。")
                badgeText: qsTr("LOG")
                accentColor: Theme.textSecondary
            }
        }
    }
}
