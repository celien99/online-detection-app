import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"
import styles

Rectangle {
    id: mainScreen
    color: Theme.bgPrimary

    property var viewModel: null

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        StatusBar {
            id: statusBar
            Layout.fillWidth: true
            lineId: viewModel ? viewModel.lineId : ""
            systemStatus: viewModel ? viewModel.systemStatus : "stopped"
            okCount: viewModel ? viewModel.okCount : 0
            ngCount: viewModel ? viewModel.ngCount : 0
            tactRate: viewModel ? viewModel.tactRate : 0.0
            lineStatus: viewModel ? viewModel.lineStatus : "unknown"
            lineConnected: viewModel ? viewModel.lineConnected : false
            lineBusy: viewModel ? viewModel.lineBusy : false
            lastTriggerResult: viewModel ? viewModel.lastTriggerResult : ""
            triggerError: viewModel ? viewModel.triggerError : ""
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            color: Theme.bgPrimary

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingMD
                anchors.rightMargin: Theme.spacingMD
                spacing: Theme.spacingSM

                Text {
                    text: qsTr("相机")
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    font.bold: true
                }

                Text {
                    text: viewModel ? qsTr("已连接 ") + connectedCameraCount(viewModel.cameraList) + "/" + viewModel.cameraList.length : qsTr("已连接 0/0")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeSM
                }

                Item { Layout.fillWidth: true }

                ActionButton {
                    buttonText: qsTr("手动触发")
                    bgColor: Theme.accent
                    implicitHeight: 32
                    Layout.preferredWidth: 104
                    enabled: viewModel && !viewModel.lineBusy
                    onClicked: viewModel.manualTrigger()
                }
            }
        }

        CameraGrid {
            Layout.fillWidth: true
            Layout.fillHeight: true
            cameraModel: viewModel ? viewModel.cameraList : []
        }
    }

    NGOverlay {
        id: ngOverlay
        anchors.fill: parent
        visible: viewModel ? viewModel.ngOverlayVisible : false
        defectType: viewModel ? viewModel.ngDefectType : ""
        confidence: viewModel ? viewModel.ngConfidence : 0.0
        cameraId: viewModel ? viewModel.ngCameraId : ""
        countdown: viewModel ? viewModel.remainingSeconds : 0
        imageVersion: viewModel ? viewModel.ngImageVersion : 0

        onConfirmNG: { if (viewModel) viewModel.acknowledgeNG(); }
        onMarkReview: { if (viewModel) viewModel.markReview(); }
        onDismissFalseAlarm: { if (viewModel) viewModel.dismissFalseAlarm(); }
    }

    Timer {
        interval: 500
        running: true
        repeat: true
        onTriggered: {
            if (viewModel) {
                viewModel.refreshTriggerState()
            }
        }
    }

    function connectedCameraCount(items) {
        var count = 0
        for (var i = 0; i < items.length; i++) {
            if (items[i].live) {
                count += 1
            }
        }
        return count
    }
}
