import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"
import styles

Rectangle {
    id: reviewScreen
    color: Theme.bgPrimary

    property var reviewModel: []
    property var viewModel: null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        // Header
        RowLayout {
            Text {
                text: qsTr("复核队列")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
                Layout.fillWidth: true
            }
            ActionButton {
                buttonText: qsTr("刷新")
                bgColor: Theme.bgTertiary
                implicitHeight: 36
                implicitWidth: 100
                onClicked: {
                    if (reviewScreen.viewModel) reviewScreen.viewModel.refresh();
                }
            }
        }

        // Summary
        Text {
            text: reviewScreen.reviewModel.length > 0
                  ? qsTr("共 ") + reviewScreen.reviewModel.length + qsTr(" 条待复核记录")
                  : qsTr("暂无待复核记录")
            color: reviewScreen.reviewModel.length > 0 ? Theme.statusWarning : Theme.textMuted
            font.pixelSize: Theme.fontSizeSM
        }

        // Review list
        ListView {
            id: reviewList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: reviewScreen.reviewModel
            clip: true
            visible: reviewScreen.reviewModel.length > 0

            delegate: Rectangle {
                width: reviewList.width
                height: 72
                color: index % 2 === 0 ? Theme.bgPrimary : Theme.bgSecondary
                border {
                    width: 1
                    color: Theme.borderDefault
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMD
                    spacing: Theme.spacingMD

                    // Info columns
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        RowLayout {
                            spacing: Theme.spacingSM
                            Text {
                                text: modelData.camera_id || ""
                                color: Theme.textPrimary
                                font.pixelSize: Theme.fontSizeSM
                                font.bold: true
                            }
                            StatusBadge {
                                badgeText: modelData.status || ""
                                badgeStatus: modelData.status === "NG" ? "ng" : "ok"
                            }
                        }
                        Text {
                            text: (modelData.defect_type || qsTr("未知"))
                                  + qsTr("  ·  置信度: ")
                                  + (modelData.confidence ? modelData.confidence.toFixed(3) : "0.000")
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                        Text {
                            text: qsTr("时间: ")
                                  + (modelData.timestamp ? new Date(modelData.timestamp * 1000).toLocaleString(Qt.locale()) : "")
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSizeXS
                        }
                    }

                    // Action buttons
                    RowLayout {
                        spacing: Theme.spacingSM

                        ActionButton {
                            buttonText: qsTr("确认缺陷")
                            bgColor: Theme.statusNG
                            implicitHeight: 32
                            implicitWidth: 90
                            font.pixelSize: Theme.fontSizeXS
                            onClicked: {
                                if (reviewScreen.viewModel) reviewScreen.viewModel.confirmAsDefect(modelData.id);
                            }
                        }
                        ActionButton {
                            buttonText: qsTr("误报忽略")
                            bgColor: Theme.statusOK
                            implicitHeight: 32
                            implicitWidth: 90
                            font.pixelSize: Theme.fontSizeXS
                            onClicked: {
                                if (reviewScreen.viewModel) reviewScreen.viewModel.dismissAsOK(modelData.id);
                            }
                        }
                    }
                }
            }
        }

        // Empty state
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgCard
            radius: Theme.radiusMD
            border { width: 1; color: Theme.borderDefault }
            visible: reviewScreen.reviewModel.length === 0

            Column {
                anchors.centerIn: parent
                spacing: Theme.spacingSM
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("暂无待复核记录")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeMD
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr('在 NG 弹窗中标记“待复核”的记录会出现在这里')
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSizeSM
                }
            }
        }
    }
}
