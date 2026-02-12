{% set tables = [
    "quickbooks__ap_ar_enhanced",
    "int_quickbooks__vendor_credit_transactions",
    "int_quickbooks__vendor_credit_double_entry",
    "int_quickbooks__sales_union",
    "int_quickbooks__sales_receipt_transactions",
    "int_quickbooks__sales_receipt_double_entry",
    "int_quickbooks__refund_receipt_transactions",
    "int_quickbooks__refund_receipt_double_entry",
    "int_quickbooks__purchase_transactions",
    "int_quickbooks__purchase_double_entry",
    "int_quickbooks__payment_double_entry",
    "int_quickbooks__journal_entry_transactions",
    "int_quickbooks__journal_entry_double_entry",
    "int_quickbooks__invoice_transactions",
    "int_quickbooks__invoice_join",
    "int_quickbooks__invoice_double_entry",
    "int_quickbooks__expenses_union",
    "int_quickbooks__deposit_transactions",
    "int_quickbooks__credit_memo_transactions",
    "int_quickbooks__credit_memo_double_entry",
    "int_quickbooks__bill_transactions",
    "int_quickbooks__bill_payment_double_entry",
    "int_quickbooks__bill_join",
    "int_quickbooks__bill_double_entry",
] %}

{% for table_name in tables %}
    {% set node = graph.nodes["model." ~ project_name ~ "." ~ table_name ] %}
    {% set raw_sql = node.raw_code | lower %}
    
    {% if "using_exchange_rate" in raw_sql %}
        select 'none' as error_message where false union all
    {% else %}
        select 'using_exchange_rate is not in {{ table_name }}' as error_message union all
    {% endif %}

{% endfor %}

select 'none' as error_message where false