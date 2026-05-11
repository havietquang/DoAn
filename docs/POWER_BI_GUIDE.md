# Power BI Guide For Olist Data Lakehouse

Tài liệu này hướng dẫn dựng dashboard Power BI cơ bản nhưng đủ giống mẫu: có KPI cards, line chart theo thời gian, bar chart top category/payment/customer state, donut chart, và phân tích seller/customer.

## 1. Mục Tiêu Dashboard

Dashboard nên có 3 trang:

| Trang | Mục tiêu | Câu hỏi trả lời |
| --- | --- | --- |
| Order Management | Theo dõi đơn hàng và thanh toán | Có bao nhiêu đơn? Doanh thu bao nhiêu? Payment type nào phổ biến? |
| Product Analysis | Phân tích sản phẩm và category | Category nào bán nhiều? Category nào doanh thu cao? |
| Sales and Customer Management | Phân tích khách hàng, state và seller | State nào tạo doanh thu cao? Seller nào hoạt động tốt? |

## 2. Kết Nối Power BI Với PostgreSQL

Trước khi mở Power BI, chạy project:

```bash
docker compose up --build
```

Sau đó trigger Airflow DAG `olist_etl_pipeline` để tạo bảng trong schema `analytics`.

Trong Power BI Desktop:

1. Chọn `Get Data`.
2. Chọn `PostgreSQL database`.
3. Nhập:
   - Server: `localhost`
   - Database: `olist_dw`
4. Chọn `Database` authentication:
   - User name: `olist`
   - Password: `olist`
5. Chọn chế độ `Import` cho dễ demo.
6. Chọn các bảng trong schema `analytics`.

Nếu Power BI yêu cầu driver PostgreSQL, cài Npgsql theo hướng dẫn của Power BI rồi mở lại Power BI Desktop.

## 3. Bảng Cần Import

Import các bảng sau:

- `fact_orders`
- `fact_order_items`
- `dim_customers`
- `dim_products`
- `dim_sellers`
- `dim_date`
- `agg_sales_monthly`
- `agg_category_performance`
- `agg_seller_performance`

Nếu muốn làm đơn giản hơn, chỉ cần:

- `fact_orders`
- `fact_order_items`
- `dim_customers`
- `dim_products`
- `dim_sellers`
- `dim_date`

Các bảng `agg_*` giúp làm chart nhanh hơn, nhưng không bắt buộc.

## 4. Relationship Model

Vào `Model view`, tạo relationship:

| From | To | Cardinality | Cross filter |
| --- | --- | --- | --- |
| `fact_orders[customer_id]` | `dim_customers[customer_id]` | Many to one | Single |
| `fact_orders[product_id]` | `dim_products[product_id]` | Many to one | Single |
| `fact_orders[seller_id]` | `dim_sellers[seller_id]` | Many to one | Single |
| `fact_orders[order_date]` | `dim_date[date_day]` | Many to one | Single |
| `fact_order_items[customer_id]` | `dim_customers[customer_id]` | Many to one | Single |
| `fact_order_items[product_id]` | `dim_products[product_id]` | Many to one | Single |
| `fact_order_items[seller_id]` | `dim_sellers[seller_id]` | Many to one | Single |
| `fact_order_items[order_date]` | `dim_date[date_day]` | Many to one | Single |

Khuyến nghị:

- Không tạo relationship trực tiếp giữa `fact_orders` và `fact_order_items` nếu chưa cần.
- Chỉ dùng một fact chính cho từng chart để tránh số bị nhân đôi.
- Với KPI tổng quan, ưu tiên `fact_orders`.
- Với category/product, ưu tiên `fact_order_items`.

## 5. DAX Measures Cơ Bản

Vào `Modeling` -> `New measure`, tạo các measure sau.

```DAX
Total Revenue = SUM(fact_orders[total_amount])
```

```DAX
Total Orders = DISTINCTCOUNT(fact_orders[order_id])
```

```DAX
Total Quantity = SUM(fact_orders[item_count])
```

```DAX
Unique Customers = DISTINCTCOUNT(fact_orders[customer_id])
```

```DAX
Active Sellers = DISTINCTCOUNT(fact_orders[seller_id])
```

```DAX
Average Order Value = DIVIDE([Total Revenue], [Total Orders])
```

```DAX
Total Freight = SUM(fact_orders[freight_value])
```

```DAX
Average Review Score = AVERAGE(fact_orders[average_review_score])
```

```DAX
Average Delivery Days = AVERAGE(fact_orders[delivery_lead_days])
```

```DAX
On Time Orders =
COUNTROWS(
    FILTER(
        fact_orders,
        fact_orders[is_delivered_on_time] = TRUE()
    )
)
```

```DAX
On Time Delivery Rate = DIVIDE([On Time Orders], [Total Orders])
```

Cho chart category theo item-level, tạo thêm:

```DAX
Item Revenue = SUM(fact_order_items[item_total_amount])
```

```DAX
Order Item Count = COUNTROWS(fact_order_items)
```

```DAX
Item Freight = SUM(fact_order_items[freight_value])
```

## 6. Trang 1: Order Management

Mục tiêu: giống phần đầu ảnh mẫu, gồm KPI cards, line chart theo thời gian, payment type, top category.

### Visual 1: Title

Text box:

```text
ORDER MANAGEMENT
```

### Visual 2: KPI Cards

Dùng `Card` visual:

- `[Total Orders]`
- `[Total Revenue]`
- `[Total Quantity]`
- `[Average Order Value]`

Format gợi ý:

- Background: trắng.
- Border: bật, màu xám nhạt.
- Category label: bật.
- Data label: màu xanh đậm hoặc xám đậm.

### Visual 3: Orders Over Time

Visual: `Line chart`

- X-axis: `dim_date[year_month]`
- Y-axis: `[Total Orders]`

Format:

- Line color: đỏ/cam.
- Data label: có thể bật nếu dữ liệu ít.
- Sort `year_month` tăng dần.

### Visual 4: Revenue Over Time

Visual: `Line chart`

- X-axis: `dim_date[year_month]`
- Y-axis: `[Total Revenue]`

Nếu muốn giống mẫu chỉ cần một line chart, dùng Orders Over Time hoặc Revenue Over Time.

### Visual 5: Payment Type Popularity

Visual: `Clustered column chart`

- X-axis: `fact_orders[primary_payment_type]`
- Y-axis: `[Total Orders]`

Sort giảm dần theo `[Total Orders]`.

### Visual 6: Top 5 Product Category With Lowest Orders

Visual: `Bar chart`

- Y-axis: `dim_products[product_category_name_english]`
- X-axis: `[Order Item Count]`
- Filter visual: Top N -> Bottom 5 theo `[Order Item Count]`

Nếu Power BI không có Bottom N trực tiếp:

1. Sort chart tăng dần theo `[Order Item Count]`.
2. Dùng visual-level filter, chọn category không blank.
3. Giữ 5 category đầu.

### Visual 7: Top 5 Product Category With Highest Orders

Visual: `Bar chart`

- Y-axis: `dim_products[product_category_name_english]`
- X-axis: `[Order Item Count]`
- Filter visual: Top N -> Top 5 theo `[Order Item Count]`

## 7. Trang 2: Product Analysis

Mục tiêu: phân tích sản phẩm/category giống phần giữa ảnh mẫu.

### Visual 1: Title

```text
PRODUCT ANALYSIS
```

### Visual 2: KPI Cards

Cards:

- `[Total Quantity]`
- `DISTINCTCOUNT(dim_products[product_category_name_english])`
- `[Item Revenue]`
- `[Average Review Score]`

Tạo measure category:

```DAX
Total Product Categories = DISTINCTCOUNT(dim_products[product_category_name_english])
```

### Visual 3: Sold Product Over Time

Visual: `Line chart`

- X-axis: `dim_date[year_month]`
- Y-axis: `[Total Quantity]`

### Visual 4: Top 10 Product Categories With Highest Revenue

Visual: `Donut chart`

- Legend: `dim_products[product_category_name_english]`
- Values: `[Item Revenue]`
- Filter: Top 10 theo `[Item Revenue]`

### Visual 5: Top 10 Product Categories With Highest Selling Quantity

Visual: `Bar chart`

- Y-axis: `dim_products[product_category_name_english]`
- X-axis: `[Order Item Count]`
- Filter: Top 10 theo `[Order Item Count]`

### Visual 6: Top 10 Product Categories With Lowest Selling Quantity

Visual: `Bar chart`

- Y-axis: `dim_products[product_category_name_english]`
- X-axis: `[Order Item Count]`
- Sort tăng dần.
- Lọc bỏ blank/null category.

## 8. Trang 3: Sales and Customer Management

Mục tiêu: phân tích doanh thu, khách hàng, state và seller.

### Visual 1: Title

```text
SALES AND CUSTOMER MANAGEMENT
```

### Visual 2: KPI Cards

Cards:

- `[Total Revenue]`
- `[Unique Customers]`
- `[Active Sellers]`
- `[Average Delivery Days]`

### Visual 3: Revenue By Customer State

Visual: `Clustered column chart`

- X-axis: `dim_customers[customer_state]`
- Y-axis: `[Total Revenue]`
- Sort giảm dần theo `[Total Revenue]`.

### Visual 4: Customers By State

Visual: `Clustered column chart`

- X-axis: `dim_customers[customer_state]`
- Y-axis: `[Unique Customers]`

### Visual 5: Active Seller By State

Visual: `Bar chart`

- Y-axis: `dim_sellers[seller_state]`
- X-axis: `[Active Sellers]`

### Visual 6: Seller Performance

Visual: `Table` hoặc `Matrix`

Fields:

- `dim_sellers[seller_state]`
- `dim_sellers[seller_city]`
- `[Total Orders]`
- `[Total Revenue]`
- `[Average Review Score]`

Sort giảm dần theo `[Total Revenue]`.

## 9. Layout Gợi Ý

Thiết lập page:

- Canvas size: `16:9`
- Background: `#F7F8FA`
- Card background: trắng
- Border: xám nhạt `#E5E7EB`
- Font: Segoe UI
- Màu chính:
  - KPI: `#4B587C`
  - Line chart: `#FF6B6B`
  - Bar chart xanh: `#4A90E2`
  - Bar chart đỏ nhạt: `#F27C7C`
  - Bar chart xanh lá: `#8BC34A`

Bố cục giống ảnh mẫu:

```text
--------------------------------------------------
| Title      | KPI 1 | KPI 2 | KPI 3 | KPI 4     |
--------------------------------------------------
| Line chart large              | Small bar chart |
--------------------------------------------------
| Bar chart left                | Bar chart right |
--------------------------------------------------
```

Với trang thứ 2 dùng donut chart bên phải. Trang thứ 3 dùng 2 column chart phía trên và bảng seller phía dưới.

## 10. Cách Tránh Sai Số Trong Power BI

Các lỗi hay gặp:

- Dùng cả `fact_orders` và `fact_order_items` trong cùng một visual rồi bị nhân đôi doanh thu.
- Relationship để `Both` làm filter chạy vòng.
- Không sort `year_month` nên line chart sai thứ tự.
- Category null làm chart có dòng blank.

Cách làm đúng:

- KPI doanh thu tổng dùng `fact_orders[total_amount]`.
- Category/product dùng `fact_order_items[item_total_amount]`.
- Relationship để `Single`.
- Với chart theo tháng, dùng `dim_date[year_month]` và sort tăng dần.
- Lọc bỏ blank category trong visual-level filter.

## 11. Checklist Hoàn Thành

- Power BI kết nối được PostgreSQL local.
- Import đủ bảng `analytics`.
- Relationship fact/dim đã đúng.
- Tạo đủ measures cơ bản.
- Trang Order Management có KPI, time series, payment type, top category.
- Trang Product Analysis có KPI, line chart, donut chart, category quantity.
- Trang Sales and Customer Management có revenue by state, customers by state, seller performance.
- Các chart không bị blank hoặc nhân đôi số.
- File `.pbix` được lưu để demo.

## 12. Câu SQL Đối Chiếu Số Với Power BI

Chạy trong PostgreSQL để kiểm tra số tổng:

```sql
select
    count(distinct order_id) as total_orders,
    round(sum(total_amount), 2) as total_revenue,
    count(distinct customer_id) as unique_customers,
    count(distinct seller_id) as active_sellers
from analytics.fact_orders;
```

Doanh thu theo tháng:

```sql
select
    d.year_month,
    round(sum(f.total_amount), 2) as total_revenue,
    count(distinct f.order_id) as total_orders
from analytics.fact_orders f
join analytics.dim_date d
    on f.order_date = d.date_day
group by d.year_month
order by d.year_month;
```

Top category theo doanh thu:

```sql
select
    p.product_category_name_english,
    round(sum(i.item_total_amount), 2) as revenue,
    count(*) as order_items
from analytics.fact_order_items i
join analytics.dim_products p
    on i.product_id = p.product_id
where p.product_category_name_english is not null
group by p.product_category_name_english
order by revenue desc
limit 10;
```
