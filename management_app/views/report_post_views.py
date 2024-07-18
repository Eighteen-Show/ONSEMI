from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from auth_app.utils import volunteer_required
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
from monitoring_app.signals import my_signal

# report 생성 기능
@login_required
@volunteer_required
def create_report(request, care_id):
    care = get_object_or_404(Care, id=care_id)
    senior = care.seniors.first()

    if request.method == 'POST':
        report = Report.objects.create(care=care, user=request.user)

        # 이미지 파일 업로드 부분
        if 'images' in request.FILES:
            image_files = request.FILES.getlist('images')
            for f in image_files:
                ReportImage.objects.create(report=report, image=f)

        # 음성 파일 업로드 및 처리 부분
        handle_audio_file_upload(request, report)

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

        my_signal.send(sender=care)
        
        report.status = '등록'
        report.save()
        return redirect('management_app:report_list')

    return render(request, 'management_app/add_report.html', {'care': care, 'senior': senior})

# report 수정 기능
@login_required
@volunteer_required
def update_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    care = get_object_or_404(Care, id=report.care_id)
    senior = care.seniors.first()
    
    if request.method == 'POST':
        # 체크박스 및 텍스트 필드 업데이트
        report.no_issue = 'no_issue' in request.POST
        report.eye = 'eye' in request.POST
        report.teeth = 'teeth' in request.POST
        report.skin = 'skin' in request.POST
        report.back = 'back' in request.POST
        report.other = 'other' in request.POST
        report.other_text = request.POST.get('other_text', '')
        report.doctor_opinion = request.POST.get('doctor_opinion', '')
        report.user_request = request.POST.get('user_request', '')

        # 이미지 삭제 처리
        delete_image_ids = request.POST.getlist('delete_images')
        for image_id in delete_image_ids:
            image = get_object_or_404(ReportImage, id=image_id, report=report)
            image.delete()

        # 새 이미지 추가
        if 'images' in request.FILES:
            for image in request.FILES.getlist('images'):
                ReportImage.objects.create(report=report, image=image)

        # 음성 파일 업로드 및 처리 부분
        handle_audio_file_upload(request, report)

        report.save()
        return redirect('management_app:report_list')

    return render(request, 'management_app/update_report.html', {'report': report, 'senior': senior})

# 음성 파일 전처리 함수
def preprocess_audio(audio_file):
    # 오디오 파일을 wav로 변환
    audio = AudioSegment.from_file(audio_file)
    wav_io = BytesIO()
    audio.export(wav_io, format='wav')
    wav_io.seek(0)
    return wav_io

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

    # 이미지를 메모리에 저장
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', pad_inches=0)
    plt.clf()
    plt.close()
    img_buffer.seek(0)

    # 이미지를 로드하고 전처리
    image = Image.open(img_buffer).convert('RGB')
    image = image.resize((224, 224))
    image_array = np.array(image).astype(np.float32) / 255.0  # 정규화
    image_array = np.expand_dims(image_array, axis=0)  # 배치 차원 추가

    # 이미지 버퍼 닫기
    img_buffer.close()

    return image_array

# 오디오 세그먼트를 예측하는 함수
def predict_audio_segments(audio_file, model_path):
    # 오디오 파일을 로드 및 변환
    wav_io = preprocess_audio(audio_file)
    audio_data, sample_rate = librosa.load(wav_io, sr=48000)
    
    # 음성 파일 버퍼 닫기
    wav_io.close()

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

def handle_audio_file_upload(request, report):
    if 'audio_file' in request.FILES:
        audio_file = request.FILES['audio_file']

        # 오디오 파일을 처리하고 예측 수행
        model_path = "savemodel_101_all_Dense_32.h5" # 가중치 파일 경로
        predictions = predict_audio_segments(audio_file, model_path)
        result = analyze_results(predictions)

        # 예측 결과 저장
        report.audio_test_result = result
        report.save()