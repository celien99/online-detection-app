import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"
import styles

Rectangle {
    id: diagnosticsScreen
    color: Theme.bgPrimary

    property var viewModel: null

    ToastNotification {
        id: toast
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Theme.spacingMD
        anchors.rightMargin: Theme.spacingMD
        z: 100
    }

    Component.onCompleted: {
        if (viewModel) {
            viewModel.refresh()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMD

            Text {
                text: qsTr("生产自检")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
            }

            Rectangle {
                Layout.preferredWidth: statusText.implicitWidth + 24
                Layout.preferredHeight: 30
                radius: Theme.radiusSM
                color: statusColor(viewModel ? viewModel.overallStatus : "unknown", true)
                border { width: 1; color: statusColor(viewModel ? viewModel.overallStatus : "unknown", false) }
                Text {
                    id: statusText
                    anchors.centerIn: parent
                    text: viewModel ? viewModel.overallStatus : "unknown"
                    color: statusColor(viewModel ? viewModel.overallStatus : "unknown", false)
                    font.pixelSize: Theme.fontSizeSM
                    font.bold: true
                }
            }

            Item { Layout.fillWidth: true }

            ActionButton {
                buttonText: qsTr("重新检查")
                bgColor: Theme.accent
                implicitHeight: 34
                Layout.preferredWidth: 108
                onClicked: {
                    if (viewModel) {
                        viewModel.refresh()
                    }
                }
            }

            ActionButton {
                buttonText: qsTr("生成验收报告")
                bgColor: Theme.accentGreen
                textColor: "#000000"
                implicitHeight: 34
                Layout.preferredWidth: 132
                onClicked: {
                    if (viewModel) {
                        var ok = viewModel.generateSiteReport()
                        toast.show(viewModel.reportMessage, ok ? "success" : "error")
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: reportColumn.implicitHeight + Theme.spacingMD * 2
            color: Theme.bgSecondary
            radius: Theme.radiusSM
            border { width: 1; color: Theme.borderDefault }

            RowLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacingMD
                spacing: Theme.spacingMD

                Rectangle {
                    Layout.preferredWidth: 72
                    Layout.preferredHeight: 28
                    radius: Theme.radiusSM
                    color: statusColor(viewModel ? viewModel.reportStatus : "idle", true)
                    border { width: 1; color: statusColor(viewModel ? viewModel.reportStatus : "idle", false) }
                    Text {
                        anchors.centerIn: parent
                        text: viewModel ? viewModel.reportStatus : "idle"
                        color: statusColor(viewModel ? viewModel.reportStatus : "idle", false)
                        font.pixelSize: Theme.fontSizeXS
                        font.bold: true
                    }
                }

                ColumnLayout {
                    id: reportColumn
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: qsTr("现场验收报告")
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeSM
                        font.bold: true
                    }
                    Text {
                        Layout.fillWidth: true
                        text: viewModel
                              ? (viewModel.reportMessage || qsTr("尚未生成报告"))
                              : qsTr("尚未生成报告")
                        color: Theme.textSecondary
                        font.pixelSize: Theme.fontSizeXS
                        elide: Text.ElideMiddle
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: viewModel && viewModel.lastReportPath !== ""
                        text: viewModel ? viewModel.lastReportPath : ""
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSizeXS
                        elide: Text.ElideMiddle
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: diagnosticsList
                anchors.fill: parent
                model: viewModel ? viewModel.items : []
                spacing: Theme.spacingSM
                clip: true
                visible: count > 0

                delegate: Rectangle {
                    width: ListView.view.width
                    height: Math.max(74, itemColumn.implicitHeight + Theme.spacingMD * 2)
                    color: Theme.bgSecondary
                    radius: Theme.radiusSM
                    border { width: 1; color: Theme.borderDefault }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingMD
                        spacing: Theme.spacingMD

                        Rectangle {
                            Layout.preferredWidth: 64
                            Layout.preferredHeight: 28
                            radius: Theme.radiusSM
                            color: statusColor(modelData.status, true)
                            border { width: 1; color: statusColor(modelData.status, false) }
                            Text {
                                anchors.centerIn: parent
                                width: parent.width - 8
                                text: modelData.status || "WARN"
                                color: statusColor(modelData.status, false)
                                font.pixelSize: Theme.fontSizeXS
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                            }
                        }

                        ColumnLayout {
                            id: itemColumn
                            Layout.fillWidth: true
                            spacing: 4

                            Text {
                                text: modelData.name || ""
                                color: Theme.textPrimary
                                font.pixelSize: Theme.fontSizeSM
                                font.bold: true
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                text: modelData.message || ""
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                            Text {
                                visible: (modelData.suggestion || "") !== ""
                                text: qsTr("建议: ") + modelData.suggestion
                                color: Theme.statusWarning
                                font.pixelSize: Theme.fontSizeXS
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }

            EmptyState {
                anchors.fill: parent
                visible: diagnosticsList.count === 0
                title: qsTr("暂无自检结果")
                message: qsTr("点击“重新检查”后会显示配置、相机、模型和存储状态。")
                badgeText: qsTr("CHECK")
                accentColor: Theme.statusWarning
            }
        }
    }

    function statusColor(status, dim) {
        if (status === "OK") return dim ? Theme.statusOKDim : Theme.statusOK
        if (status === "FAIL") return dim ? Theme.statusNGDim : Theme.statusNG
        return dim ? Theme.statusWarningDim : Theme.statusWarning
    }
}
