import QtQuick
import QtQuick.Layouts
import "components"
import styles

Item {
    id: grid

    property var cameraModel: []
    property string gridLayout: "2x2"
    signal openPreview(string cameraId)

    GridLayout {
        anchors.fill: parent
        visible: grid.cameraModel.length > 0
        columns: {
            var parts = grid.gridLayout.split("x");
            return parts.length === 2 ? parseInt(parts[0]) : 2;
        }
        rows: {
            var parts = grid.gridLayout.split("x");
            return parts.length === 2 ? parseInt(parts[1]) : 2;
        }
        rowSpacing: 4
        columnSpacing: 4

        Repeater {
            model: grid.cameraModel

            CameraTile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                cameraId: modelData.cameraId || ""
                cameraStatus: modelData.status || "ok"
                defectLabel: modelData.defectLabel || ""
                live: modelData.live || false
                frameVersion: modelData.frameVersion || 0
                onOpenPreview: function(cameraId) {
                    grid.openPreview(cameraId)
                }
            }
        }
    }

    EmptyState {
        anchors.fill: parent
        visible: grid.cameraModel.length === 0
        title: qsTr("未配置相机")
        message: qsTr("当前产线没有可显示的相机通道，请在设置页或型号管理中检查相机配置。")
        badgeText: qsTr("CAMERA")
        accentColor: Theme.statusWarning
    }
}
