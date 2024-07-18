from django.shortcuts import render, get_object_or_404, redirect
from cart_app.forms import CartAddProductForm
from ..models import Category, Product
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ..forms import CommentForm, ReplyForm
from django.views.decorators.http import require_POST
from orders_app.models import OrderItem
from django.db.models import Avg
from django.core.paginator import Paginator

import pandas as pd


@login_required
def product_list(request, category_slug=None):
    
    # 예측 결과 불러오기 및 정렬
    price_predict = pd.read_csv('./result.csv')
    price_predict.sort_values(by='3', ascending=True)
    
    # 예측 결과 데이터 전처리
    price_predict['3'] = round(price_predict['3'] * 100, 2) # 가격 변동률 100분위로 변경
    price_predict['2'] = price_predict['2'].astype(int)     # 변동된 가격 int로 변경
    
    # 가격 상승 상품 3개 저장
    increases = price_predict.iloc[: 3].values.tolist()
    
    # 가격 하락 상품 3개 저장
    decreases = price_predict.iloc[-1: -4: -1].values.tolist()
    
    category = None
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    recent_products_ids = request.session.get('recent_products', [])
    # 빈 리스트를 생성합니다.
    recent_products = []

    # for 문을 사용하여 각 ID로 Product 객체를 쿼리하고 리스트에 저장합니다.
    for product_id in recent_products_ids:
        product = Product.objects.get(id=product_id)
        recent_products.insert(0,product)

    return render(request,
                  'shop/product/list.html',
                  {'category': category,
                   'categories': categories,
                   'products': products,
                   'recent_products': recent_products,
                   'increases': increases,
                   'decreases': decreases})


@login_required
def product_detail(request, id, slug):
    product = get_object_or_404(Product,
                                id=id,
                                slug=slug,
                                available=True)
    cart_product_form = CartAddProductForm()
    stock_alert = product.stock <= 10

    comment_form = CommentForm()
    reply_form = ReplyForm()

    # 부모 댓글 필터링
    comments = product.comments.filter(parent__isnull=True)

    # 평균 별점 계산
    average_rating = comments.aggregate(Avg('rating'))['rating__avg'] or 0

    # 최근 본 상품에 추가
    recent_products = request.session.get('recent_products', [])
    if product.id not in recent_products:
        recent_products.append(product.id)
        request.session['recent_products'] = recent_products

    # 사용자 구매 여부 확인
    has_purchased = OrderItem.objects.filter(order__user=request.user, product=product).exists()

    paginator = Paginator(comments, 5)  
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'product': product,
        'cart_product_form': cart_product_form,
        'stock_alert': stock_alert,
        'comment_form': comment_form,
        'reply_form': reply_form,
        'comments': comments,
        'has_purchased': has_purchased,
        'average_rating': average_rating,
        'page_obj': page_obj,
    }
    return render(request,'shop/product/detail.html',context)


@login_required
def add_to_recent_products(request, id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=id, available=True)
        recent_products = request.session.get('recent_products', [])
        if product.id not in recent_products:
            recent_products.append(product.id)
            request.session['recent_products'] = recent_products
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'failed'}, status=400)


@login_required
def remove_from_recent_products(request, id):
    recent_products = request.session.get('recent_products', [])
    if id in recent_products:
        recent_products.remove(id)
        request.session['recent_products'] = recent_products
    return redirect('shop_app:product_list')


@login_required
@require_POST
def like_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if product.likes.filter(id=request.user.id).exists():
        product.likes.remove(request.user)
    else:
        product.likes.add(request.user)
    return JsonResponse({'likes': product.total_likes()})
