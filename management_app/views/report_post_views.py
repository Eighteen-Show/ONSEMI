from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from management_app.models import Senior, Care, Report, ReportImage
from django.http import JsonResponse
from django.urls import reverse

@login_required
def create_report(request, care_id):
    care = get_object_or_404(Care, id=care_id)
    if care.care_state not in ['APPROVED']:
        return redirect('management_app:report_list')

    if request.method == 'POST':
        report = Report.objects.create(care=care, user=request.user)

         # 이미지 파일 업로드 부분
        if 'images' in request.FILES:
            image_files = request.FILES.getlist('images')  # 다중 파일을 가져옴
            for f in image_files:
                ReportImage.objects.create(report=report, image=f)

        # 텍스트 입력
        report.doctor_opinion = request.POST.get('doctor_opinion', '')
        report.user_request = request.POST.get('user_request', '')

        # 이상 부위 체크박스 결과 저장
        report.no_issue = 'no_issue' in request.POST
        report.eye = 'eye' in request.POST
        report.teeth = 'teeth' in request.POST
        report.skin = 'skin' in request.POST
        report.back = 'back' in request.POST
        report.other = 'other' in request.POST
        report.other_text = request.POST.get('other_text', '')
        
        care.care_state = 'COMPLETED'
        care.save()
        
        report.status = '등록'
        report.save()
        return redirect('management_app:report_list')
    
    return render(request, 'management_app/add_report.html', {'care': care})

@login_required
def manage_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)

    if request.method == 'POST':
        
        previous_url = request.META.get('HTTP_REFERER')
        # 이미지 추가 처리
        if 'add_image' in request.POST:
        #files = request.FILES.getlist('file')
            for f in request.FILES.getlist('images'):
                ReportImage.objects.create(report=report, image=f)
            return redirect(previous_url)
            
        # 텍스트 업데이트 처리
        report.doctor_opinion = request.POST.get('doctor_opinion', '')
        report.user_request = request.POST.get('user_request', '')

        # # 상태 변경 처리
        # if 'change_status' in request.POST:
        #     report.status = request.POST.get('status', '')

        # 체크박스 업데이트 처리
        report.no_issue = 'no_issue' in request.POST
        report.eye = 'eye' in request.POST
        report.teeth = 'teeth' in request.POST
        report.skin = 'skin' in request.POST
        report.back = 'back' in request.POST
        report.other = 'other' in request.POST
        report.other_text = request.POST.get('other_text', '')

        # 이미지 삭제 처리
        if 'delete_image' in request.POST:
            image_id = request.POST.get('delete_image')
            image = get_object_or_404(ReportImage, id=image_id)
            image.delete()
            return redirect(previous_url)

        # # 모든 이미지 삭제 처리
        # if 'delete_all_images' in request.POST:
        #     report.images.all().delete()

        # 보고서 삭제 처리
        if 'delete_report' in request.POST:
            report.delete()
            return redirect('management_app:report_list')

        report.status = '등록'
        report.save()
        return redirect('management_app:report_list')

    return render(request, 'management_app/update_report.html', {
        'report': report,
        'images': report.images
    })


# @login_required
# def delete_report(request, report_id):
#     report = get_object_or_404(Report, id=report_id)
#     report.delete()
#     return redirect('management_app:report_list')

@login_required
def delete_image(request, image_id):
    image = get_object_or_404(Report.images, id=image_id)
    report_id = image.report.id
    image.delete()
    return redirect('management_app:manage_report', report_id=report_id)

@login_required
def delete_all_files(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    report.images.all().delete()
    return redirect('management_app:manage_report', report_id=report.id)

@login_required
def update_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    if request.method == 'POST':
        # 업데이트 로직 추가
        pass
    return render(request, 'management_app/update_report.html', {'report': report})

@login_required
def refresh_pending_reports(request):
    # 미등록 보고서 생성 로직 추가
    pending_cares = Care.objects.filter(care_state='APPROVED').exclude(id__in=Report.objects.values('care_id'))
    for care in pending_cares:
        Report.objects.create(care=care, user=request.user, status='미등록')

    return JsonResponse({'message': '미등록 보고서가 생성되었습니다.'})
