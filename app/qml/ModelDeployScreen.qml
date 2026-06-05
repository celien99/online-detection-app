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
        ignoreUnknownSignals: true
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
            ActionButton {
                buttonText: qsTr("手动导入")
                bgColor: Theme.bgTertiary
                Layout.preferredWidth: 112
                implicitHeight: 36
                onClicked: importDialog.open()
            }
            ActionButton {
                buttonText: qsTr("从离线平台同步")
                bgColor: Theme.accentGreen
                textColor: "#000000"
                Layout.preferredWidth: 150
                implicitHeight: 36
                onClicked: {
                    if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.syncFromPlatform();
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
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: Theme.spacingMD
                        anchors.rightMargin: Theme.spacingMD
                        spacing: 4
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.fillWidth: true
                            text: modelData.label
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignHCenter
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.fillWidth: true
                            text: {
                                if (modelData.valueKey === "syncStatus") return modelDeployScreen.viewModel ? modelDeployScreen.viewModel.syncStatus : "offline";
                                if (modelData.valueKey === "modelCount") return modelDeployScreen.viewModel ? String(modelDeployScreen.viewModel.modelFiles.length) : "0";
                                if (modelData.valueKey === "lastSyncTime") return modelDeployScreen.viewModel ? (modelDeployScreen.viewModel.lastSyncTime || qsTr("从未")) : qsTr("从未");
                                return "";
                            }
                            color: modelData.color
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignHCenter
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
                model: [qsTr("全部类型"), "patchcore", "filter_classifier", "rules"]
                onCurrentTextChanged: {
                    if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.setFilterType(
                        currentIndex === 0 ? "" : currentText
                    );
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: fileList
                anchors.fill: parent
                model: modelDeployScreen.viewModel ? modelDeployScreen.viewModel.modelFiles : []
                spacing: Theme.spacingSM
                visible: count > 0
                clip: true

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
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.spacingSM
                                Text {
                                    text: modelData.camera_id || ""
                                    color: Theme.textSecondary
                                    font.pixelSize: Theme.fontSizeXS
                                    Layout.maximumWidth: 160
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: modelData.model_type || ""
                                    color: Theme.textMuted
                                    font.pixelSize: Theme.fontSizeXS
                                    Layout.maximumWidth: 180
                                    elide: Text.ElideRight
                                }
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
                            ActionButton {
                                buttonText: modelData.is_active ? qsTr("已激活") : qsTr("激活")
                                bgColor: modelData.is_active ? Theme.bgTertiary : Theme.accentGreen
                                textColor: modelData.is_active ? Theme.textMuted : "#000000"
                                implicitWidth: modelData.is_active ? 68 : 56
                                implicitHeight: 28
                                enabled: !modelData.is_active
                                font.pixelSize: Theme.fontSizeXS
                                onClicked: modelDeployScreen.viewModel.activateVersion(modelData.id)
                            }
                            ActionButton {
                                visible: !modelData.is_active
                                buttonText: qsTr("删除")
                                bgColor: Qt.rgba(0.973, 0.318, 0.286, 0.16)
                                textColor: Theme.statusNG
                                implicitWidth: 52
                                implicitHeight: 28
                                font.pixelSize: Theme.fontSizeXS
                                onClicked: modelDeployScreen.viewModel.deleteModelFile(modelData.id)
                            }
                        }
                    }
                }
            }

            EmptyState {
                anchors.fill: parent
                visible: fileList.count === 0
                title: qsTr("暂无模型文件")
                message: qsTr("可手动导入模型文件，或从离线平台同步可用版本。")
                badgeText: qsTr("MODEL")
                accentColor: Theme.accent
            }
        }
    }

    IndustrialDialog {
        id: importDialog
        title: qsTr("导入模型文件")
        acceptText: qsTr("选择文件")
        showCancel: true
        onAccepted: fileDialog.open()

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                Layout.fillWidth: true
                text: qsTr("相机 ID")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
                font.weight: Font.Medium
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                color: importCamInput.activeFocus ? Qt.rgba(1, 1, 1, 0.06) : Theme.cardGlass
                radius: Theme.radiusSM
                border { width: 1; color: importCamInput.activeFocus ? Theme.accent : Theme.cardGlassBorder }
                Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
                TextInput {
                    id: importCamInput
                    anchors.fill: parent
                    anchors.leftMargin: 12; anchors.rightMargin: 12
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    activeFocusOnPress: true
                    selectByMouse: true
                    text: "cam_front"
                }
            }

            Text {
                Layout.fillWidth: true
                text: qsTr("模型类型")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
                font.weight: Font.Medium
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                color: importTypeMouse.pressed ? Qt.rgba(1, 1, 1, 0.10)
                       : importTypeMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.06)
                       : Theme.cardGlass
                radius: Theme.radiusSM
                border {
                    width: 1
                    color: importTypePopup.visible ? Theme.accent
                           : importTypeMouse.containsMouse ? Theme.borderStrong
                           : Theme.cardGlassBorder
                }
                Behavior on color { ColorAnimation { duration: Theme.animFast } }
                Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

                Text {
                    id: importTypeLabel
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: importTypeCombo.currentText
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: "▼"
                    color: importTypePopup.visible ? Theme.accent : Theme.textSecondary
                    font.pixelSize: 9
                }
                MouseArea {
                    id: importTypeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: importTypePopup.open()
                }
                Popup {
                    id: importTypePopup
                    y: parent.height + 4
                    x: 0
                    width: parent.width
                    padding: 4
                    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                    background: Rectangle {
                        color: Theme.bgSecondary
                        radius: Theme.radiusMD
                        border { width: 1; color: Theme.accent }
                    }
                    contentItem: ColumnLayout {
                        spacing: 2
                        Repeater {
                            model: ["patchcore", "filter_classifier", "rules"]
                            delegate: Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 34
                                radius: Theme.radiusSM
                                color: importTypeCombo.currentIndex === index ? Theme.accentDim
                                       : (hoverHandler.containsMouse ? (hoverHandler.pressed ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(1, 1, 1, 0.06)) : "transparent")
                                Behavior on color { ColorAnimation { duration: Theme.animFast } }
                                Text {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData
                                    color: importTypeCombo.currentIndex === index ? Theme.accent : Theme.textPrimary
                                    font.pixelSize: Theme.fontSizeSM
                                    font.bold: importTypeCombo.currentIndex === index
                                }
                                MouseArea {
                                    id: hoverHandler
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        importTypeCombo.currentIndex = index;
                                        importTypePopup.close();
                                    }
                                }
                            }
                        }
                    }
                }
                ComboBox {
                    id: importTypeCombo
                    visible: false
                    model: ["patchcore", "filter_classifier", "rules"]
                    currentIndex: 0
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
                modelDeployScreen.viewModel.importModelFile(
                    importCamInput.text || "cam_front",
                    importTypeCombo.currentText,
                    String(selectedFile)
                );
            }
        }
    }
}
