from mturk.models import FullVideoTask

def get_active_video_turk_task(video_id):
    tasks = FullVideoTask.objects.filter(video__id = video_id, closed = False)

    if len(tasks) > 1:
        raise Exception('More than one full video task for video {}'.format(video_id))
    elif len(tasks) == 1:
        return tasks[0]
        
    return None
