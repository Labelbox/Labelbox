from django.db import models
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from tqdm import tqdm
from datetime import datetime

from .mturk_api import Server
from annotator.models import Video
import time
import math

import logging
import os

logger = logging.getLogger()


mturk = Server(settings.AWS_ID, settings.AWS_KEY, settings.URL_ROOT, settings.MTURK_SANDBOX)


class Task(models.Model):
    hit_id = models.CharField(max_length=64, blank=True,
        help_text="ID on MTurk. Auto-populated when publishing")
    hit_group = models.CharField(max_length=64, blank=True,
        help_text=("Group ID on Mturk. "
            "HITs with same title/description usually are placed in the same group by MTurk. "
            "Auto-populated when publishing."))
    metrics = models.TextField(blank=True)
    duration = 10800 # 3 hours
    lifetime = 2592000 # 30 days
    worker_id = models.CharField(max_length=64, blank=True,
        help_text="ID of worker who submitted this HIT")
    assignment_id = models.CharField(max_length=64, blank=True,
        help_text="ID of matching between this task and a worker. Used for authentication")
    time_completed = models.DateTimeField(null=True, blank=True)
    bonus = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    sandbox = models.BooleanField(default=settings.MTURK_SANDBOX)
    message = models.CharField(max_length=256, blank=True)
    email_trail = models.TextField(blank=True)
    last_email_sent_date = models.DateTimeField(null=True, blank=True)
    closed = models.BooleanField(default=False)
    paid = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def publish(self):
        if settings.MTURK_SANDBOX != self.sandbox:
            raise Exception("settings.MTURK_SANDBOX != self.sandbox")
        if self.video.verified:
            self.video.verified = False
            self.video.save()
        response = mturk.create_hit(self.title, self.description, self.url,
            self.pay, self.duration, self.lifetime)
        self.hit_id = response.values['hitid']
        self.hit_group = response.values['hittypeid']
        self.save()

    def complete(self, worker_id, assignment_id, metrics):
        self.worker_id = worker_id
        self.assignment_id = assignment_id
        self.metrics = metrics
        self.bonus = self.calculate_bonus()
        self.message = settings.MTURK_BONUS_MESSAGE
        self.time_completed = datetime.now()

        self.paid = False
        self.save()

    def send_email(self, subject, message):
        if (self.worker_id == ''):
            raise Exception("No worked id to send email to for FullVideoTask({})".format(id))

        mturk.email(self.worker_id, subject, message)
        self.last_email_sent_date = datetime.now()
        self.email_trail += "{}================================================{}".format(os.linesep, os.linesep)
        self.email_trail += "Date: {}{}".format(self.last_email_sent_date.strftime("%c"), os.linesep)
        self.email_trail += "Subject: {}{}".format(subject, os.linesep)
        self.email_trail += "--------------------------------------------------{}".format(os.linesep)
        self.email_trail += message
        self.email_trail += os.linesep

        self.save()

    def approve_assignment(self, bonus, message):
        if self.assignment_id == None:
            raise Exception("Cannot approve task - no work has been done on Turk")

        if bonus > 0:
            mturk.bonus(self.worker_id, self.assignment_id, bonus, message)

        mturk.accept(self.assignment_id, message)

    def reject_assignment(self, message):
        if self.assignment_id == None:
            raise Exception("Cannot reject task - no work has been done on Turk")

        mturk.reject(self.assignment_id, message)

    def blockWorker(self):
        if self.worker_id == None:
            raise Exception("Cannot reject task - no work has been done on Turk")

        mturk.block(self.worker_id, settings.MTURK_BLOCK_MESSAGE)

    def archive_turk_hit(self):
        res = mturk.disable(self.hit_id)

    @classmethod
    def calculate_bonus(self):
        return 0

    @classmethod
    def batch_create_and_publish(cls, videos, **kwargs):
        created = []
        for video in tqdm(videos):
            task = cls(video=video, **kwargs)
            task.save()
            task.publish()
        return created

    @classmethod
    def valid_hit_id(cls, id):
        if id is None:
            return False
        try:
            item = cls.get_by_hit_id(id)
            return True
        except ObjectDoesNotExist:
            return settings.DEBUG

    @classmethod
    def get_by_hit_id(cls, id):
        items = []
        for task_type in cls.__subclasses__():
            try:
                items.append(task_type.objects.get(hit_id=id))
            except ObjectDoesNotExist:
                pass
        if len(items) > 1:
            raise MultipleObjectsReturned()
        elif len(items) == 0:
            raise ObjectDoesNotExist()
        else:
            return items[0]


class FullVideoTask(Task):
    video = models.ForeignKey(Video)
    title = settings.MTURK_TITLE
    description = settings.MTURK_DESCRIPTION
    pay = settings.MTURK_BASE_PAY
    bonus_per_box = settings.MTURK_BONUS_PER_BOX

    @property
    def url(self):
        return reverse('video', args=[self.video.id])

    def __str__(self):
        return self.video.filename or str(self.video)

    def calculate_bonus(self):
        boxes  = self.video.count_keyframes()
        num_cents = boxes * self.bonus_per_box
        return num_cents


class SingleFrameTask(Task):
    video = models.ForeignKey(Video)
    time = models.FloatField()
    title = "Image Annotation"
    description = "Draw boxes around all objects of interest in an image, with bonus per object"
    pay = 0.01
    bonus_per_box = 0.005

    def calculate_bonus(self):
        boxes = self.video.count_keyframes(at_time=self.time)
        num_cents = ((boxes - 1) * self.bonus_per_box + self.pay) * 100
        return math.ceil(num_cents) / 100

    @property
    def url(self):
        return reverse('video', args=[self.video.id]) + '?s={0}&amp;e={0}'.format(self.time)

    def __str__(self):
        return '{:.2f} of {}'.format(self.time, self.video.filename)
