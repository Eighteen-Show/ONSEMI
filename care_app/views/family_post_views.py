from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db import transaction
from auth_app.models import User
from care_app.models import Care, Senior

# Create your views here.

# 1 -> easy
# user(보호자)가 노인을 등록하는 기능 (예상 : html파일 1+개?)
#       -> 위에거 수정하는 페이지(html1개+)


# 2 -> normal
# user(보호자)가 Care를 등록하는 기능(예상 :html파일 1+개?) -> 어려움
#       -> 위에거 수정하는 페이지(html1개+)

# 3 ->개어렵
# user(봉사자)가 user(보호자)가 올린 Care를 확인하는 = 조회하는 기능(예상 :html 1+개?)
# 여러 방면으로 조회할 수 있어야함 ( 노인 카테고리로 조회, 오름차순, 내림차순, or 유저별로, 지역별로, 날짜별로 오름차순)
# NOT_APPROVED, CONFIRMED, APPROVED
# 4 ->hard
# user(보호자)가 자신이 올린 Care를 확인하는 기능(예상: html 1개 이상)
# 여러 방면으로 조회할 수 있어야함
# 위에거랑 같은데 유저별은 없겠죠?
# NOT_APPROVED, CONFIRMED, APPROVED


# @login_required
def add_care(request):
    if request.method == "GET":
        user = request.user
        user = User.objects.get(pk=user.id)
        user_senior_list = user.senior_set.all()
        context = {"seniors": user_senior_list}
        return render(request, "care_app/add_care.html", context)

    if request.method == "POST":
        care_type = request.POST.get("care_type")
        title = request.POST.get("title")
        content = request.POST.get("content")
        senior = request.POST.get("senior")

        user = request.user
        user = get_object_or_404(User, pk=user.id)

        care = Care(
            care_type=care_type,
            title=title,
            content=content,
            user_id=user.id,
        )
        care.save()

        user_senior = Senior.objects.get(pk=senior)
        care.seniors.add(user_senior)

        return redirect("/")


# @login_required
def update_care(request):
    if request.method == "GET":
        return render(request, "care_app/update_care.html")

    if request.method == "POST":
        pass


# @login_required
def add_senior(request):
    if request.method == "GET":
        context = {"ages": [i for i in range(1, 120)]}
        return render(request, "care_app/add_senior.html", context)

    if request.method == "POST":
        name = request.POST.get("name")
        address = request.POST.get("address")
        age = request.POST.get("age")
        gender = request.POST.get("gender")
        phone_number = request.POST.get("phone_number")
        has_alzheimers = request.POST.get("has_alzheimers")
        has_parkinsons = request.POST.get("has_parkinsons")
        user = request.user

        user = User.objects.get(pk=user.id)
        senior = Senior(
            name=name,
            address=address,
            age=age,
            gender=gender,
            phone_number=phone_number,
            use_id=user,
        )
        senior.save()

        return redirect("/")


# @login_required
def update_senior(request):
    if request.method == "GET":
        return render(request, "care_app/update_senior.html")

    if request.method == "POST":
        pass