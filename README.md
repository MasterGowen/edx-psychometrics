# edx-psychometrics

## Установка:

1. Установка пакета edx-psychometrics: `sudo /edx/bin/pip.edxapp install git+https://github.com/MasterGowen/edx-psychometrics@master`

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
