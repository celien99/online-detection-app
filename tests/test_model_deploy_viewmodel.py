"""Tests for ModelDeployViewModel model-scoped runtime behavior."""
from __future__ import annotations

from pathlib import Path

from app.services.config_persistence import ConfigPersistenceService
from app.services.model_file_service import ModelFileService
from app.services.seat_model_service import SeatModelService
from app.viewmodels.model_deploy_viewmodel import ModelDeployViewModel


class FakePlatformSync:
    def check_health(self) -> bool:
        return True


def test_model_deploy_viewmodel_filters_and_refreshes_by_seat_model(tmp_path: Path) -> None:
    persistence = ConfigPersistenceService(str(tmp_path / "test.db"))
    seat_models = SeatModelService(persistence)
    seat_models.create_model("SEAT_A", "型号A")
    seat_models.create_model("SEAT_B", "型号B")
    seat_models.set_default("SEAT_A")
    for model_id in ("SEAT_A", "SEAT_B"):
        seat_models.add_camera(
            model_id,
            {
                "camera_id": "CAM_1",
                "type": "file_watcher",
                "source": "./input",
                "patchcore_model_path": "./old.pt",
            },
        )
    model_files = ModelFileService(persistence, models_dir=str(tmp_path / "models"))
    seat_a_model = tmp_path / "seat_a.pt"
    seat_a_model.write_bytes(b"seat-a")
    seat_b_model = tmp_path / "seat_b.pt"
    seat_b_model.write_bytes(b"seat-b")
    model_files.import_file("CAM_1", "patchcore", str(seat_a_model), seat_model_id="SEAT_A")
    model_files.import_file("CAM_1", "patchcore", str(seat_b_model), seat_model_id="SEAT_B")
    refreshed = []
    vm = ModelDeployViewModel(
        model_files,
        FakePlatformSync(),  # type: ignore[arg-type]
        seat_models,
        on_runtime_models_changed=refreshed.append,
    )

    assert vm.selectedSeatModelId == "SEAT_A"
    assert [item["file_name"] for item in vm.modelFiles] == ["seat_a.pt"]
    assert vm.activeRuntimeVersions[0]["file_name"] == "seat_a.pt"

    vm.setSeatModel("SEAT_B")

    assert [item["file_name"] for item in vm.modelFiles] == ["seat_b.pt"]
    assert vm.activeRuntimeVersions[0]["file_name"] == "seat_b.pt"
    assert [item["id"] for item in vm.cameraOptions] == ["", "CAM_1"]

    vm.verifyActiveVersions()

    assert refreshed == []

