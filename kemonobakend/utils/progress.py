from rich.progress import (
    Progress, TextColumn, BarColumn, TimeRemainingColumn, 
    DownloadColumn, TransferSpeedColumn, SpinnerColumn, Task, 
    TaskID
)
from typing import Union

class ProgressBase(Progress):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def add_task(self,
            description: str,
            file_name: str = None,
            start: bool = True,
            total: float | None = 100,
            completed: int = 0,
            visible: bool = True,
            **fields) -> 'ProgressTask':
        
        if not self.live.is_started:
            self.start()
        fields.update({'filename': file_name})
        task = super().add_task(total=total, completed=completed, description=description, start=start, visible=visible, **fields)
        return ProgressTask(self, task)
    
    def remove_task(self, task_id: Union[TaskID, 'ProgressTask']) -> None:
        if isinstance(task_id, ProgressTask):
            task_id = task_id._id
        return super().remove_task(task_id)
    
class NormalProgress(ProgressBase):
    def __init__(self, *columns, **kwargs):
        super().__init__(*columns, **kwargs)
    
    @classmethod
    def get_default_columns(cls):
        return (
            TextColumn("[bold blue][progress.description]{task.description}", justify="left"),
            BarColumn(bar_width=None),
            
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            "•",
            TimeRemainingColumn(),
            "•",
            SpinnerColumn()
        )
    
    def __enter__(self) -> 'NormalProgress':
        return super().__enter__()
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        super().__exit__(exc_type, exc_val, exc_tb)

class DownloadProgress(ProgressBase):
    def __init__(self, *columns, speed_estimate_period=6, **kwargs):
        super().__init__(*columns, speed_estimate_period=speed_estimate_period, **kwargs)
    
    @classmethod
    def get_default_columns(cls):
        return (
            TextColumn("[bold blue][progress.description]{task.description} {task.fields[filename]}", justify="left"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
            "•",
            SpinnerColumn()
        )
        
class ProgressTask:
    def __init__(self, progress: DownloadProgress, taskId):
        self._id = taskId
        self._progress = progress  
    
    def start(self):
        self._progress.start_task(self._id)
    def stop(self):
        self._progress.stop_task(self._id)
        
    def update(
            self, *, 
            total=None, 
            completed=None, 
            advance=None, 
            description=None, 
            visible=None, 
            refresh=False, 
            **fields
        ):
        self._progress.update(self._id, total=total, completed=completed, advance=advance, description=description, visible=visible, refresh=refresh, **fields)
    def advance(self, advance=1):
        self._progress.advance(self._id, advance=advance)
    def remove(self):
        self._progress.remove_task(self._id)
    
    def get_speed(self):
        task = self._progress._tasks.get(self._id)
        if task is not None:
            return task.speed
    
    def __enter__(self):
        self.start()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
    