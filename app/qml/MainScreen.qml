import QtQuick
import QtQuick.Layouts
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

        onConfirmNG: { if (viewModel) viewModel.acknowledgeNG(); }
        onMarkReview: { if (viewModel) viewModel.markReview(); }
        onDismissFalseAlarm: { if (viewModel) viewModel.dismissFalseAlarm(); }
    }
}
