# -*- coding: utf-8 -*-

from rest_framework import viewsets
from rest_framework.generics import GenericAPIView

from task.api.task.serializers import TaskSerializer
from task.models import Task
from utils.request_utils import AuthPermission, search, handle_order
from json import dumps
from django.http import HttpResponse
from django.db.models import Count


# Created by: guangda.lee
# Created on: 2019/3/27
# Function: 任务视图


# ViewSets define the view behavior.
class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [AuthPermission, ]

    @handle_order
    def get_queryset(self):
        def try_str_to_int(s, default=0):
            try:
                return int(s)
            except ValueError:
                return default

        from django.db.models import Q
        from users.common import user_by_token, is_admin
        user = user_by_token(self.request)
        queryset = Task.objects.filter(~Q(status='cancelled'))
        if not is_admin(user):
            queryset = queryset.filter(creator_id=user.id)
        if 'status' in self.request.query_params:
            queryset = queryset.filter(status=self.request.query_params['status'])
        queryset = search(self.request, queryset,
                          lambda qs, keyword: qs.filter(
                              Q(pk=try_str_to_int(keyword)) | Q(creator__auth__last_name__icontains=keyword) | Q(
                                  name__icontains=keyword)))
        return queryset


# 任务统计
class TaskSumView(GenericAPIView):
    permission_classes = (AuthPermission,)

    def get(self, request, *args, **kwargs):
        rs = TaskViewSet(request=request).get_queryset().values('status').annotate(total=Count('status'))
        result = dict()
        for r in rs:
            if r['status'] in result:
                result[r['status']] += r['total']
            else:
                result[r['status']] = r['total']

        return HttpResponse(dumps({
            # 'data': list(map(lambda item:[item, result[item]], result))
            'data': list(map(lambda item:{"name": item, "value": result[item]},result))
        }))
