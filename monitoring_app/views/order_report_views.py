from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.timezone import make_aware
from django.utils.dateparse import parse_date
from django.http import HttpResponse
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from ..forms import FilterForm
from orders_app.models import Order, OrderItem
from shop_app.models import Category
from datetime import datetime, time
import csv
from management_app.models import Care 

# 맥 전용 한글 폰트
from matplotlib import rc
rc('font', family='AppleGothic')

####################################################################################
@login_required
def generate(request):
    form = FilterForm(request.POST or None)
    categories = Category.objects.all()
    
    graph_url = None
    pie_chart_url = None

    if request.method == 'POST' and form.is_valid():
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        category_order = form.cleaned_data.get('category_order')
        category_service = form.cleaned_data.get('category_service')
        
        orders = Order.objects.filter(email=request.user.email)
        if start_date:
            start_date = make_aware(datetime.combine(start_date, time.min))
            orders = orders.filter(created__gte=start_date)
        if end_date:
            end_date = make_aware(datetime.combine(end_date, time.max))
            orders = orders.filter(created__lte=end_date)
        if category_order and category_order != 'all':
            orders = orders.filter(items__product__category__name=category_order).distinct()

####################################################################################
        data = []
        for order in orders:
            for item in order.items.all():
                data.append({
                    'Order ID': order.id,
                    'Product': item.product.name,
                    'Category': item.product.category.name,
                    'Price': float(item.price),
                    'Quantity': item.quantity,
                    'Total Cost': float(item.price * item.quantity),
                    'Created': order.created.isoformat(),
                })
        df = pd.DataFrame(data)
        df['Created'] = pd.to_datetime(df['Created'], format='ISO8601', errors='coerce')
        df['Quantity'] = df['Quantity'].astype(float)

####################################################################################
        # 서비스 요청 데이터를 데이터프레임으로 변환
        data_care = []
        cares = Care.objects.filter(user_id=request.user.id)
        if start_date:
            cares = cares.filter(datetime__gte=start_date)
        if end_date:
            cares = cares.filter(datetime__lte=end_date)
        if category_service and category_service != 'all':
            cares = cares.filter(care_type=category_service)

        total_cares = cares.count()
        approved_cares = cares.filter(care_state='APPROVED').count()
        
        approval_rate = 0
        if total_cares > 0:
            approval_rate = (approved_cares / total_cares) * 100
        
        for care in cares:
            data_care.append({
                'care_type': care.care_type,
                'datetime': care.datetime.isoformat(),
            })
        df_care = pd.DataFrame(data_care)
        df_care['datetime'] = pd.to_datetime(df_care['datetime'], format='ISO8601', errors='coerce')

####################################################################################
        if not df_care.empty:
            # 꺾은선 그래프 생성 (주간 단위)
            plt.figure(figsize=(10, 6))
            df_care['Week'] = df_care['datetime'].dt.to_period('W').apply(lambda r: r.start_time)
            weekly_data = df_care.groupby(['Week', 'care_type']).size().unstack().fillna(0)
            for column in weekly_data.columns:
                plt.plot(weekly_data.index, weekly_data[column], marker='o', label=column)
            plt.legend(title='요청 종류')
            plt.xlabel('기간')
            plt.ylabel('요청 수')
            plt.xticks(rotation=45)
            plt.tight_layout()

            # 그래프 이미지를 메모리에 저장
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            image_png = buffer.getvalue()
            buffer.close()

            graph_url = base64.b64encode(image_png).decode('utf-8')
            graph_url = 'data:image/png;base64,' + graph_url

####################################################################################
        # 전체 데이터 기반 원형 그래프 생성
        all_orders = Order.objects.filter(email=request.user.email)
        if start_date:
            all_orders = all_orders.filter(created__gte=start_date)
        if end_date:
            all_orders = all_orders.filter(created__lte=end_date)
        
        all_data = []
        for order in all_orders:
            for item in order.items.all():
                all_data.append({
                    'Category': item.product.category.name,
                    'Quantity': item.quantity,
                })
        all_df = pd.DataFrame(all_data)
        all_df['Quantity'] = all_df['Quantity'].astype(float)

        if not all_df.empty:
            plt.figure(figsize=(10, 6))
            category_counts = all_df.groupby('Category')['Quantity'].sum()
            plt.pie(category_counts, labels=category_counts.index, autopct='%1.1f%%', startangle=140)
            plt.axis('equal')

            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            buffer.seek(0)
            image_png = buffer.getvalue()
            buffer.close()

            pie_chart_url = base64.b64encode(image_png).decode('utf-8')
            pie_chart_url = 'data:image/png;base64,' + pie_chart_url

        for record in data:
            record['Price'] = float(record['Price'])
            record['Total Cost'] = float(record['Total Cost'])

        request.session['filtered_orders'] = data
        request.session['filtered_cares'] = data_care
        request.session['category_order'] = category_order
        request.session['category_service'] = category_service
        request.session['approval_rate'] = approval_rate

    return render(request, 'monitoring_app/generate.html', {
        'form': form, 
        'categories': categories, 
        'graph_url': graph_url, 
        'pie_chart_url': pie_chart_url
    })

####################################################################################
@login_required
def csv_view(request):
    data_type = request.GET.get('type')
    if data_type == 'care':
        filtered_cares = request.session.get('filtered_cares', [])
        category_service = request.session.get('category_service')
        approval_rate = request.session.get('approval_rate', 0)
        if category_service and category_service != 'all':
            filtered_cares = [care for care in filtered_cares if care['care_type'] == category_service]
        return render(request, 'monitoring_app/csv_view.html', {
            'filtered_cares': filtered_cares, 
            'data_type': 'care',
            'approval_rate': approval_rate,
        })
    else:
        filtered_orders = request.session.get('filtered_orders', [])
        category_order = request.session.get('category_order')
        if category_order and category_order != 'all':
            filtered_orders = [order for order in filtered_orders if order['Category'] == category_order]
        return render(request, 'monitoring_app/csv_view.html', {
            'filtered_orders': filtered_orders, 
            'data_type': 'order'
        })

####################################################################################
@login_required
def download_order_csv(request):
    filtered_orders = request.session.get('filtered_orders', [])
    category_order = request.session.get('category_order')
    if category_order and category_order != 'all':
        filtered_orders = [order for order in filtered_orders if order['Category'] == category_order]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="filtered_orders.csv"'

    writer = csv.writer(response)
    writer.writerow(['Order ID', 'Product', 'Category', 'Price', 'Quantity', 'Total Cost', 'Created'])

    for order in filtered_orders:
        writer.writerow([order['Order ID'], order['Product'], order['Category'], order['Price'], order['Quantity'], order['Total Cost'], order['Created']])

    return response

####################################################################################
@login_required
def download_care_csv(request):
    filtered_cares = request.session.get('filtered_cares', [])
    category_service = request.session.get('category_service')
    if category_service and category_service != 'all':
        filtered_cares = [care for care in filtered_cares if care['care_type'] == category_service]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="filtered_cares.csv"'

    writer = csv.writer(response)
    writer.writerow(['Care Type', 'Datetime'])

    for care in filtered_cares:
        writer.writerow([care['care_type'], care['datetime']])

    return response


# from django.shortcuts import render, redirect
# from django.contrib.auth.decorators import login_required
# from django.utils.timezone import make_aware
# from django.utils.dateparse import parse_date
# from django.http import HttpResponse
# import pandas as pd
# import matplotlib.pyplot as plt
# from io import BytesIO
# import base64
# from ..forms import FilterForm
# from orders_app.models import Order, OrderItem
# from shop_app.models import Category
# from datetime import datetime, time
# import csv
# from management_app.models import Care 

# # 맥 전용 한글 폰트
# from matplotlib import rc
# rc('font', family='AppleGothic')

# ####################################################################################
# @login_required
# def generate(request):
#     form = FilterForm(request.POST or None)
#     categories = Category.objects.all()
    
#     graph_url = None
#     pie_chart_url = None

#     if request.method == 'POST' and form.is_valid():
#         start_date = form.cleaned_data.get('start_date')
#         end_date = form.cleaned_data.get('end_date')
#         category_order = form.cleaned_data.get('category_order')
#         category_service = form.cleaned_data.get('category_service')
        
#         orders = Order.objects.filter(email=request.user.email)
#         if start_date:
#             start_date = make_aware(datetime.combine(start_date, time.min))
#             orders = orders.filter(created__gte=start_date)
#         if end_date:
#             end_date = make_aware(datetime.combine(end_date, time.max))
#             orders = orders.filter(created__lte=end_date)
#         if category_order and category_order != 'all':
#             orders = orders.filter(items__product__category__name=category_order).distinct()

# ####################################################################################
#         data = []
#         for order in orders:
#             for item in order.items.all():
#                 data.append({
#                     'Order ID': order.id,
#                     'Product': item.product.name,
#                     'Category': item.product.category.name,
#                     'Price': float(item.price),
#                     'Quantity': item.quantity,
#                     'Total Cost': float(item.price * item.quantity),
#                     'Created': order.created.isoformat(),
#                 })
#         df = pd.DataFrame(data)
#         df['Created'] = pd.to_datetime(df['Created'], format='ISO8601', errors='coerce')
#         df['Quantity'] = df['Quantity'].astype(float)

# ####################################################################################
#         # 서비스 요청 데이터를 데이터프레임으로 변환
#         data_care = []
#         cares = Care.objects.filter(user_id=request.user.id, care_state='APPROVED')
#         if start_date:
#             cares = cares.filter(datetime__gte=start_date)
#         if end_date:
#             cares = cares.filter(datetime__lte=end_date)
#         if category_service and category_service != 'all':
#             cares = cares.filter(care_type=category_service)

#         for care in cares:
#             data_care.append({
#                 'care_type': care.care_type,
#                 'datetime': care.datetime.isoformat(),
#             })
#         df_care = pd.DataFrame(data_care)
#         df_care['datetime'] = pd.to_datetime(df_care['datetime'], format='ISO8601', errors='coerce')

# ####################################################################################
#         if not df_care.empty:
#             # 꺾은선 그래프 생성 (주간 단위)
#             plt.figure(figsize=(10, 6))
#             df_care['Week'] = df_care['datetime'].dt.to_period('W').apply(lambda r: r.start_time)
#             weekly_data = df_care.groupby(['Week', 'care_type']).size().unstack().fillna(0)
#             for column in weekly_data.columns:
#                 plt.plot(weekly_data.index, weekly_data[column], marker='o', label=column)
#             plt.legend(title='요청 종류')
#             plt.xlabel('기간')
#             plt.ylabel('요청 수')
#             plt.xticks(rotation=45)
#             plt.tight_layout()

#             # 그래프 이미지를 메모리에 저장
#             buffer = BytesIO()
#             plt.savefig(buffer, format='png')
#             buffer.seek(0)
#             image_png = buffer.getvalue()
#             buffer.close()

#             graph_url = base64.b64encode(image_png).decode('utf-8')
#             graph_url = 'data:image/png;base64,' + graph_url

# ####################################################################################
#         # 전체 데이터 기반 원형 그래프 생성
#         all_orders = Order.objects.filter(email=request.user.email)
#         if start_date:
#             all_orders = all_orders.filter(created__gte=start_date)
#         if end_date:
#             all_orders = all_orders.filter(created__lte=end_date)
        
#         all_data = []
#         for order in all_orders:
#             for item in order.items.all():
#                 all_data.append({
#                     'Category': item.product.category.name,
#                     'Quantity': item.quantity,
#                 })
#         all_df = pd.DataFrame(all_data)
#         all_df['Quantity'] = all_df['Quantity'].astype(float)

#         if not all_df.empty:
#             plt.figure(figsize=(10, 6))
#             category_counts = all_df.groupby('Category')['Quantity'].sum()
#             plt.pie(category_counts, labels=category_counts.index, autopct='%1.1f%%', startangle=140)
#             plt.axis('equal')

#             buffer = BytesIO()
#             plt.savefig(buffer, format='png')
#             buffer.seek(0)
#             image_png = buffer.getvalue()
#             buffer.close()

#             pie_chart_url = base64.b64encode(image_png).decode('utf-8')
#             pie_chart_url = 'data:image/png;base64,' + pie_chart_url

#         for record in data:
#             record['Price'] = float(record['Price'])
#             record['Total Cost'] = float(record['Total Cost'])

#         request.session['filtered_orders'] = data
#         request.session['filtered_cares'] = data_care
#         request.session['category_order'] = category_order
#         request.session['category_service'] = category_service

#     return render(request, 'monitoring_app/generate.html', {
#         'form': form, 
#         'categories': categories, 
#         'graph_url': graph_url, 
#         'pie_chart_url': pie_chart_url
#     })

# ####################################################################################
# @login_required
# def csv_view(request):
#     data_type = request.GET.get('type')
#     if data_type == 'care':
#         filtered_cares = request.session.get('filtered_cares', [])
#         category_service = request.session.get('category_service')
#         if category_service and category_service != 'all':
#             filtered_cares = [care for care in filtered_cares if care['care_type'] == category_service]
#         return render(request, 'monitoring_app/csv_view.html', {
#             'filtered_cares': filtered_cares, 
#             'data_type': 'care'
#         })
#     else:
#         filtered_orders = request.session.get('filtered_orders', [])
#         category_order = request.session.get('category_order')
#         if category_order and category_order != 'all':
#             filtered_orders = [order for order in filtered_orders if order['Category'] == category_order]
#         return render(request, 'monitoring_app/csv_view.html', {
#             'filtered_orders': filtered_orders, 
#             'data_type': 'order'
#         })

# ####################################################################################
# @login_required
# def download_order_csv(request):
#     filtered_orders = request.session.get('filtered_orders', [])
#     category_order = request.session.get('category_order')
#     if category_order and category_order != 'all':
#         filtered_orders = [order for order in filtered_orders if order['Category'] == category_order]

#     response = HttpResponse(content_type='text/csv')
#     response['Content-Disposition'] = 'attachment; filename="filtered_orders.csv"'

#     writer = csv.writer(response)
#     writer.writerow(['Order ID', 'Product', 'Category', 'Price', 'Quantity', 'Total Cost', 'Created'])

#     for order in filtered_orders:
#         writer.writerow([order['Order ID'], order['Product'], order['Category'], order['Price'], order['Quantity'], order['Total Cost'], order['Created']])

#     return response

# ####################################################################################
# @login_required
# def download_care_csv(request):
#     filtered_cares = request.session.get('filtered_cares', [])
#     category_service = request.session.get('category_service')
#     if category_service and category_service != 'all':
#         filtered_cares = [care for care in filtered_cares if care['care_type'] == category_service]

#     response = HttpResponse(content_type='text/csv')
#     response['Content-Disposition'] = 'attachment; filename="filtered_cares.csv"'

#     writer = csv.writer(response)
#     writer.writerow(['Care Type', 'Datetime'])

#     for care in filtered_cares:
#         writer.writerow([care['care_type'], care['datetime']])

#     return response