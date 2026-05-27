import QtQuick
import QtQuick.Layouts

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
            height: 40
            lineId: viewModel ? viewModel.lineId : ""
            systemStatus: viewModel ? viewModel.systemStatus : "stopped"
            okCount: viewModel ? viewModel.okCount : 0
            ngCount: viewModel ? viewModel.ngCount : 0
            tactRate: viewModel ? viewModel.tactRate : 0.0
        }

        CameraGrid {
            id: cameraGrid
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 2
            rows: 2
        }
    }

    NGOverlay {
        id: ngOverlay
        anchors.fill: parent
        visible: viewModel ? viewModel.ngOverlayVisible : false
        defectType: viewModel ? viewModel.ngDefectType : ""
        confidence: viewModel ? viewModel.ngConfidence : 0.0
        cameraId: viewModel ? viewModel.ngCameraId : ""

        onConfirmNG: { if (viewModel) viewModel.acknowledgeNG(); }
        onMarkReview: { if (viewModel) viewModel.markReview(); }
        onDismissFalseAlarm: { if (viewModel) viewModel.dismissFalseAlarm(); }
    }
}
