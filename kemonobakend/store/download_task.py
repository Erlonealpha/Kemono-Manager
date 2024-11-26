
from kemonobakend.downloader.download import DownloadTask
from .base import StoreBase

class DownloadTaskStore(StoreBase):
    def add_download_tasks(self, download_tasks: list):
        data = self.load()
        data.extend(download_tasks)
        self.dump(data)
    
    def add_download_task(self, download_task: DownloadTask):
        data = self.load()
        data.append(download_task)
        self.dump(data)
    
    def get_all_unfinished_download_tasks(self):
        return 
    
    def remove_download_task(self, download_task: DownloadTask):
        pass
    
    def download_task_done(self, download_task: DownloadTask):
        pass
    
    def download_task_failed(self, download_task: DownloadTask):
        pass
    
    def download_task_cancelled(self, download_task: DownloadTask):
        pass

    def load(self):
        d = super().load()
        if d is None:
            return []
        return d
