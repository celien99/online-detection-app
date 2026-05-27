import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"
import styles

Rectangle {
    id: modelDeployScreen
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

    Connections {
        target: modelDeployScreen.viewModel
        function onToast(message, level) { toast.show(message, level); }
    }

    Component.onCompleted: {
        if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.checkPlatformHealth();
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("模型部署")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                radius: Theme.radiusSM
                color: Theme.accentDim
                implicitWidth: 130; implicitHeight: 36
                Text {
                    anchors.centerIn: parent
                    text: qsTr("📂 手动导入")
                    color: Theme.accent
                    font.pixelSize: Theme.fontSizeSM
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: fileDialog.open()
                }
            }
            Rectangle {
                radius: Theme.radiusSM
                color: Theme.accentGreenDim
                implicitWidth: 150; implicitHeight: 36
                Text {
                    anchors.centerIn: parent
                    text: qsTr("🔄 从离线平台同步")
                    color: Theme.accentGreen
                    font.pixelSize: Theme.fontSizeSM
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.syncFromPlatform();
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMD
            Repeater {
                model: [
                    { label: qsTr("离线平台"), valueKey: "syncStatus", color: Theme.accentGreen },
                    { label: qsTr("本地模型"), valueKey: "modelCount", color: Theme.accent },
                    { label: qsTr("最近同步"), valueKey: "lastSyncTime", color: Theme.statusWarning }
                ]
                delegate: Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 70
                    color: Theme.cardGlass
                    radius: Theme.radiusMD
                    border { width: 1; color: Theme.cardGlassBorder }
                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text: modelData.label
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                        Text {
                            text: {
                                if (modelData.valueKey === "syncStatus") return modelDeployScreen.viewModel ? modelDeployScreen.viewModel.syncStatus : "offline";
                                if (modelData.valueKey === "modelCount") return modelDeployScreen.viewModel ? String(modelDeployScreen.viewModel.modelFiles.length) : "0";
                                if (modelData.valueKey === "lastSyncTime") return modelDeployScreen.viewModel ? (modelDeployScreen.viewModel.lastSyncTime || qsTr("从未")) : qsTr("从未");
                                return "";
                            }
                            color: modelData.color
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSM
            Text { text: qsTr("筛选:"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
            ComboBox {
                id: cameraFilter
                model: [qsTr("全部相机")]
                onCurrentTextChanged: {
                    if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.setFilterCamera(
                        currentIndex === 0 ? "" : currentText
                    );
                }
            }
            ComboBox {
                id: typeFilter
                model: [qsTr("全部类型"), "efficientad", "filter_classifier", "calibration_normalizer", "calibration_projector"]
                onCurrentTextChanged: {
                    if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.setFilterType(
                        currentIndex === 0 ? "" : currentText
                    );
                }
            }
        }

        ListView {
            id: fileList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: modelDeployScreen.viewModel ? modelDeployScreen.viewModel.modelFiles : []
            spacing: Theme.spacingSM

            delegate: Rectangle {
                width: ListView.view.width
                implicitHeight: 72
                color: modelData.is_active ? Theme.accentGreenDim : Theme.cardGlass
                radius: Theme.radiusMD
                border { width: 1; color: modelData.is_active ? Theme.accentGreen : Theme.cardGlassBorder }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMD
                    spacing: Theme.spacingMD

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: modelData.file_name || modelData.id
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                        }
                        RowLayout {
                            spacing: Theme.spacingSM
                            Text { text: modelData.camera_id || ""; color: Theme.textSecondary; font.pixelSize: Theme.fontSizeXS }
                            Text { text: modelData.model_type || ""; color: Theme.textMuted; font.pixelSize: Theme.fontSizeXS }
                            Text {
                                text: modelData.platform_version ? ("v" + modelData.platform_version) : ""
                                color: Theme.accent
                                font.pixelSize: Theme.fontSizeXS
                                visible: text !== ""
                            }
                            Text {
                                text: modelData.sha256 ? modelData.sha256.substring(0, 8) + "..." : ""
                                color: Theme.textMuted
                                font.pixelSize: Theme.fontSizeXS
                                visible: text !== ""
                            }
                        }
                    }

                    RowLayout {
                        spacing: Theme.spacingXS
                        Rectangle {
                            radius: Theme.radiusSM
                            color: modelData.is_active ? Theme.bgTertiary : Theme.accentGreenDim
                            implicitWidth: modelData.is_active ? 56 : 48
                            implicitHeight: 28
                            Text {
                                anchors.centerIn: parent
                                text: modelData.is_active ? qsTr("已激活") : qsTr("激活")
                                color: modelData.is_active ? Theme.textMuted : Theme.accentGreen
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: !modelData.is_active
                                onClicked: modelDeployScreen.viewModel.activateVersion(modelData.id)
                            }
                        }
                        Rectangle {
                            radius: Theme.radiusSM
                            color: Qt.rgba(0.973, 0.318, 0.286, 0.1)
                            implicitWidth: 40; implicitHeight: 28
                            visible: !modelData.is_active
                            Text {
                                anchors.centerIn: parent
                                text: qsTr("删除")
                                color: Theme.statusNG
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: modelDeployScreen.viewModel.deleteModelFile(modelData.id)
                            }
                        }
                    }
                }
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: qsTr("选择模型文件")
        nameFilters: [qsTr("Model files (*.pt *.pth *.onnx)"), qsTr("All files (*)")]
        onAccepted: {
            if (modelDeployScreen.viewModel && selectedFile) {
                modelDeployScreen.viewModel.importModelFile("", "efficientad", String(selectedFile));
            }
        }
    }
}
