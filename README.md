# edx-psychometrics

## Установка:

1. Установка `пакета edx-psychometrics`: `sudo /edx/bin/pip.edxapp install git+https://github.com/MasterGowen/edx-psychometrics@master`

2. `lms/envs/aws.py:`
```
FEATURES["ALLOW_PSY_REPORT_DOWNLOADS"] = True
if FEATURES.get("ALLOW_PSY_REPORT_DOWNLOADS"):
    OPTIONAL_APPS += ("edx-psychometrics",)
```

3. `/lms/djangoapps/instructor/views/instructor_dashboard.py`: 
```
if settings.FEATURES.get("ALLOW_PSY_REPORT_DOWNLOADS"):
    section_data['get_psychometrics_data_url'] = reverse('get_psychometrics_data', kwargs={'course_id': unicode(course_key)})
```

4. `/lms/djangoapps/instructor/views/api_urls.py`
```
from django.conf import settings

if settings.FEATURES.get("ALLOW_PSY_REPORT_DOWNLOADS"):
   urlpatterns += url(r'get_psychometrics_data',  'edx_psychometrics.api.get_psychometrics_data', name='get_psychometrics_data')
 ```
5. Добавление кнопки загрузки данных в шаблон instructor_dashboard (`/lms/templates/instructor/instructor_dashboard_2`):
```
%if settings.FEATURES.get('ALLOW_PSY_REPORT_DOWNLOADS') or section_data['access']['admin']:
 <div class="psychometrics">
  <hr>
  <h3 class="hd hd-3">${_("Psychometrics")}</h3>
    <p>${_("Click to generate an archive with psychometrics data.")}</p>
    <p>
      <input type="button" name="get-psychometrics-data" class="async-report-btn" value="${_("Generate psychometrics data")}" data-endpoint="${ section_data['get_psychometrics_data_url'] }"/>
    </p>
 </div>
%endif
``` 
6. Перезапуск edxapp и edxapp_worker:
```
/edx/bin/supervisorctl restart edxapp:
/edx/bin/supervisorctl restart edxapp_worker:
```

## Испольование:

Кнопка запуска задачи генерации архива содержащего психометрические данные.
.. image:: .readmeimg/st1.png
