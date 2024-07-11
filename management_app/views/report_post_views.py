from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from management_app.models import Senior, Care, Report, ReportImage
from django.http import JsonResponse
from django.urls import reverse
import numpy as np
import librosa
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from io import BytesIO
from tensorflow.keras.models import Model
from tensorflow.keras.models import load_model
from django.core.files.storage import default_storage
from pydub import AudioSegment
from io import BytesIO
import os

# ##### 윈도우 #####
# https://www.gyan.dev/ffmpeg/builds/에서 ffmpeg-git-full.7z 다운로드 받고, 경로 수정
# ffmpeg 경로 설정
AudioSegment.converter = r"C:\Users\prime\Downloads\설치파일\Install\ffmpeg-2024-07-07-git-0619138639-full_build\ffmpeg-2024-07-07-git-0619138639-full_build\bin\ffmpeg.exe"
AudioSegment.ffprobe = r"C:\Users\prime\Downloads\설치파일\Install\ffmpeg-2024-07-07-git-0619138639-full_build\ffmpeg-2024-07-07-git-0619138639-full_build\bin\ffprobe.exe"

# 환경 변수 설정
os.environ["PATH"] += os.pathsep + r"C:\Users\prime\Downloads\설치파일\Install\ffmpeg-2024-07-07-git-0619138639-full_build\ffmpeg-2024-07-07-git-0619138639-full_build\bin"

# ##### #####

@login_required
def create_report(request, care_id):
    care = get_object_or_404(Care, id=care_id)
    if care.care_state not in ['APPROVED']:
        return redirect('management_app:report_list')

    if request.method == 'POST':
        report = Report.objects.create(care=care, user=request.user)

        # 이미지 파일 업로드 부분
        if 'images' in request.FILES:
            image_files = request.FILES.getlist('images')
            for f in image_files:
                ReportImage.objects.create(report=report, image=f)

        # 음성 파일 업로드 및 처리 부분
        if 'audio_file' in request.FILES:
            audio_file = request.FILES['audio_file']
            audio_path = default_storage.save('tmp/' + audio_file.name, audio_file)
            audio_path = default_storage.path(audio_path)

            # 오디오 파일을 처리하고 예측 수행
            model_path = "D:\Aivle\parkinson_voice_test.keras"
            predictions = predict_audio_segments(audio_path, model_path)
            result = analyze_results(predictions)

            # 예측 결과 저장
            report.audio_test_result = result  # 이진 분류를 가정하고 필요에 따라 조정
            report.save()

            # 임시 파일 삭제
            os.remove(audio_path)

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
            for f in request.FILES.getlist('images'):
                ReportImage.objects.create(report=report, image=f)
            return redirect(previous_url)

        # 음성 파일 업로드 및 처리 부분
        if 'audio_file' in request.FILES:
            audio_file = request.FILES['audio_file']
            audio_path = default_storage.save('tmp/' + audio_file.name, audio_file)
            audio_path = default_storage.path(audio_path)

            # 오디오 파일을 처리하고 예측 수행
            model_path = "D:\Aivle\parkinson_voice_test.keras"
            predictions = predict_audio_segments(audio_path, model_path)
            result = analyze_results(predictions)

            # 예측 결과 저장
            report.audio_test_result = result  # 이진 분류를 가정하고 필요에 따라 조정
            report.save()

            # 임시 파일 삭제
            os.remove(audio_path)

        # 텍스트 업데이트 처리
        report.doctor_opinion = request.POST.get('doctor_opinion', '')
        report.user_request = request.POST.get('user_request', '')

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

@login_required
def delete_image(request, image_id):
    image = get_object_or_404(ReportImage, id=image_id)
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
    pending_cares = Care.objects.filter(care_state='APPROVED').exclude(id__in=Report.objects.values('care_id'))
    for care in pending_cares:
        Report.objects.create(care=care, user=request.user, status='미등록')

    return JsonResponse({'message': '미등록 보고서가 생성되었습니다.'})

# 음성 파일 전처리 함수
def preprocess_audio(audio_path):
    # 오디오 파일을 wav로 변환
    audio = AudioSegment.from_file(audio_path)
    wav_path = os.path.splitext(audio_path)[0] + '.wav'
    audio.export(wav_path, format='wav')
    return wav_path

# 오디오 세그먼트를 전처리하여 이미지로 변환하는 함수
def preprocess_segment(audio_segment, sample_rate):
    # Mel-spectrogram 생성 및 이미지 변환
    S = librosa.feature.melspectrogram(y=audio_segment, sr=sample_rate, n_mels=256)
    S_DB = librosa.power_to_db(S, ref=np.max)

    fig, ax = plt.subplots()
    ax.axes.get_xaxis().set_visible(False)
    ax.axes.get_yaxis().set_visible(False)
    librosa.display.specshow(S_DB, sr=sample_rate, x_axis='time', y_axis='mel', ax=ax)
    plt.axis('off')
    plt.margins(0)
    file_name = 'temp_image.png'
    plt.savefig(file_name, bbox_inches='tight', pad_inches=0)
    plt.clf()
    plt.close()

    # 이미지를 로드하고 전처리
    image = Image.open(file_name).convert('RGB')
    image = image.resize((224, 224))
    image_array = np.array(image).astype(np.float32) / 255.0  # 정규화
    image_array = np.expand_dims(image_array, axis=0)  # 배치 차원 추가

    return image_array

# 오디오 세그먼트를 예측하는 함수
def predict_audio_segments(audio_path, model_path):
    # 오디오 파일을 로드 및 변환
    wav_path = preprocess_audio(audio_path)
    audio_data, sample_rate = librosa.load(wav_path, sr=48000)
    
    # 모델 로드
    model = load_model(model_path)
    
    segment_duration = sample_rate  # 1초에 해당하는 샘플 수
    results = []

    for i in range(5):
        start_sample = i * segment_duration
        end_sample = start_sample + segment_duration
        audio_segment = audio_data[start_sample:end_sample]
        
        # 오디오 세그먼트 전처리 및 예측
        image_array = preprocess_segment(audio_segment, sample_rate)
        prediction = model.predict(image_array)
        results.append(prediction[0][0])

    return results

# 예측 결과를 분석하는 함수
def analyze_results(predictions):
    high_risk_count = sum(pred >= 0.5 for pred in predictions)
    if high_risk_count >= 3:
        return "병원에 방문하셔서 진단을 받는 것을 추천드립니다"
    else:
        return "정상입니다"