from django.urls import path

from . import views as v

urlpatterns = [
    path("assessments/", v.AssessmentListCreateView.as_view()),
    path("assessments/draft/", v.DraftView.as_view()),
    path("assessments/<uuid:pk>/", v.AssessmentDetailView.as_view()),
    path("home/", v.HomeView.as_view()),
    path("export/data/", v.ExportDataView.as_view()),
]
