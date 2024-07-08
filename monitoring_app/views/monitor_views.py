from django.shortcuts import render,reverse
from management_app.models import Care, Senior, Report, ReportImage
from auth_app.models import User
   
def family_monitor(request):
    sort_by = request.GET.get("sort_by", "datetime")
    order = request.GET.get("order", "asc")
    selected_senior_id = request.GET.get('selected_senior_id', '')
    selected_care_state = request.GET.get('care_state', '')
    selected_order = request.GET.get('order', 'desc')
   
    # 현재 로그인한 사용자의 ID
    user_id = request.user.id
   
    if order == "desc":
        sort_by = "-" + sort_by
   
    # 현재 로그인한 사용자의 Care 객체만 필터링
    cares = Care.objects.filter(user_id=user_id)
   
    if selected_senior_id:
        cares = cares.filter(seniors__id=selected_senior_id)
    if selected_care_state:
        cares = cares.filter(care_state=selected_care_state)
    if selected_order == 'asc':
        cares = cares.order_by('datetime')
    else:
        cares = cares.order_by('-datetime')
    seniors = Senior.objects.filter(user_id=user_id)
   
    cares = cares.order_by(sort_by)
    users = User.objects.all()  # 모든 사용자 정보 가져오기

    selected_senior = None
    if selected_senior_id:
        selected_senior = Senior.objects.get(id=selected_senior_id)
   
    reports = Report.objects.filter(care__in=cares)
    sorted_reports = reports.order_by('-created_at')  # created_at 등 원하는 필드로 정렬
   
    context = {
        "cares": cares,
        "users": users,
        "selected_user": user_id,
        'selected_senior_id': selected_senior_id,
        'selected_care_state': selected_care_state,
        'selected_order': selected_order,
        "seniors": seniors,
        "selected_senior": selected_senior,
        "reports" : sorted_reports,
    }
    
    return render(request, "monitoring_app/family_monitor.html", context)

def family_monitor_image(request,report_id):
    reports = Report.objects.filter(id=report_id)
    context = {"reports":reports}
    
    return render(request, "monitoring_app/care_image.html", context)