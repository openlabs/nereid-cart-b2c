==================================
Nereid Shipping Scenario
==================================

=============
General Setup
=============

Imports::

    >>> from decimal import Decimal
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import config, Model, Wizard
    >>> from nereid import Nereid

Create database::

    >>> DBNAME = ':memory:'
    >>> config = config.set_trytond(DBNAME, database_type='sqlite')

Install Nereid Checkout::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([('name', '=', 'nereid_cart_b2c')])
    >>> len(modules)
    1

    >>> Module.button_install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('start')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> Company = Model.get('company.company')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> company.name = 'OTCL'
    >>> company.currency, = Currency.find([('code', '=', 'EUR')])
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> today = datetime.date.today()
    >>> fiscalyear = FiscalYear(name='%s' % today.year)
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_sequence = Sequence(name='%s' % today.year,
    ...     code='account.move',
    ...     company=company)
    >>> post_move_sequence.save()
    >>> fiscalyear.post_move_sequence = post_move_sequence
    >>> invoice_sequence = SequenceStrict(name='%s' % today.year,
    ...     code='account.invoice',
    ...     company=company)
    >>> invoice_sequence.save()
    >>> fiscalyear.out_invoice_sequence = invoice_sequence
    >>> fiscalyear.in_invoice_sequence = invoice_sequence
    >>> fiscalyear.out_credit_note_sequence = invoice_sequence
    >>> fiscalyear.in_credit_note_sequence = invoice_sequence
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)
    True

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> AccountJournal = Model.get('account.journal')
    >>> account_template, = AccountTemplate.find([('parent', '=', False)])
    >>> create_chart_account = Wizard('account.account.create_chart_account')
    >>> create_chart_account.execute('account')
    >>> create_chart_account.form.account_template = account_template
    >>> create_chart_account.form.company = company
    >>> create_chart_account.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> create_chart_account.form.account_receivable = receivable
    >>> create_chart_account.form.account_payable = payable
    >>> create_chart_account.execute('create_properties')
    >>> stock_journal, = AccountJournal.find([('code', '=', 'STO')])

Create parties::

    >>> Party = Model.get('party.party')
    >>> Address = Model.get('party.address')
    >>> ContactMechanism = Model.get('party.contact_mechanism')
    >>> customer = Party(name='Customer', company=company)
    >>> customer.save() 
    >>> email = ContactMechanism(type='email', value='user@example.com', 
    ...     party=customer)
    >>> email.save()
    >>> customer.addresses.append(Address(
    ...     name='Customer Address', email=email, password='password'))
    >>> customer.save()

Create Guest User::

    >>> Party = Model.get('party.party')
    >>> Address = Model.get('party.address')
    >>> ContactMechanism = Model.get('party.contact_mechanism')
    >>> guest = Party(name='Guest', company=company)
    >>> guest.save() 
    >>> email = ContactMechanism(type='email', value='guest@example.com', 
    ...     party=guest)
    >>> email.save()
    >>> guest_address = Address(
    ...     name='Guest Address', email=email, 
    ...     password='password', party=guest)
    >>> guest_address.save()
    >>> guest.addresses.append(guest_address)
    >>> guest.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder')
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create Templates::

    >>> LangObj = Model.get('ir.lang')
    >>> english, = LangObj.find([('code', '=', 'en_US')])
    >>> Template = Model.get('nereid.template')
    >>> temp_template_id = Template(
    ...     name='temp-replacement.jinja', language=english,
    ...     source=' Test ')
    >>> temp_template_id.save()
    >>> login_template = Template(
    ...     name='login.jinja', language=english,
    ...     source=' ')
    >>> login_template.save()
    >>> cart_template = Template(
    ...     name='shopping-cart.jinja', language=english,
    ...     source='Cart:{{ cart.id }},{{get_cart_size()|round|int}},{{cart.sale.total_amount}}')
    >>> cart_template.save()
    >>> product_template = Template(
    ...     name='product.jinja', language=english,
    ...     source=' ')
    >>> product_template.save()
    >>> category_template = Template(
    ...     name='category.jinja', language=english,
    ...     source=' ')
    >>> category_template.save()
    >>> product_list_template = Template(
    ...     name='product-list.jinja', language=english,
    ...     source=' ')
    >>> product_list_template.save()
    >>> category_list_template = Template(
    ...     name='category-list.jinja', language=english,
    ...     source=' ')
    >>> category_list_template.save()
    >>> for template in ('account', 'sales', 'sale', 'invoice', 'invoices', 'shipment', 'shipments'):
    ...     account_template = Template(
    ...         name='%s.jinja' % template, language=english,
    ...         source=' ')
    ...     account_template.save()

Create category::

    >>> ProductCategory = Model.get('product.category')
    >>> category = ProductCategory(name='Category')
    >>> category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> product.name = 'product 1'
    >>> product.category = category
    >>> product.default_uom = unit
    >>> product.type = 'stockable'
    >>> product.purchasable = True
    >>> product.salable = True
    >>> product.list_price = Decimal('10')
    >>> product.cost_price = Decimal('5')
    >>> product.account_expense = expense
    >>> product.account_revenue = revenue
    >>> product.account_journal_stock_input = stock_journal
    >>> product.account_journal_stock_output = stock_journal
    >>> product.save()

Setup Site::

    >>> Country = Model.get('country.country')
    >>> Currency = Model.get('currency.currency')
    >>> Rate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> rate = Rate(currency=currencies[0], rate=Decimal('1.0'))
    >>> rate.save()
    >>> countries = [c.id for c in Country.find([('code', 'in', ('IN', 'US'))])]
    >>> site = NereidSite(name='Test Site', 
    ...     company=company.id, countries=countries,
    ...     product_template=product_list_template, currencies=currencies,
    ...     category_template=category_list_template,
    ...     default_language = english)
    >>> site.save()

Load the WSGI App::

    >>> from nereid import Nereid
    >>> app = Nereid(
    ...     DATABASE_NAME=DBNAME,
    ...     TRYTON_CONFIG='trytond.conf',
    ...     SITE=site.name, GUEST_USER=guest_address.id)
    >>> app.debug=True
    >>> app.site
    u'Test Site'

Allow access without login ::

    >>> with app.test_client() as c:
    ...     cart_response = c.get('/cart')
    ...     cart_response
    <Response streamed [200 OK]>

Call the cart with two different applications and assert they are not equal::

    >>> with app.test_client() as c:
    ...     cart_response_2 = c.get('/cart')
    ...     cart_response_2
    <Response streamed [200 OK]>
    >>> cart_response.data == cart_response_2.data
    False
    
Check if the Sale Order is created::

    >>> Sale = Model.get('sale.sale')
    >>> sales = Sale.find([])
    >>> len(sales)
    0

Add an item to the cart::

     >>> with app.test_client() as c:
     ...     c.post('/cart/add', data={
     ...         'product': product.id,
     ...         'quantity': 10,
     ...     })
     <Response streamed [302 FOUND]>

Check if the Sale Order is created::

    >>> Sale = Model.get('sale.sale')
    >>> sales = Sale.find([])
    >>> len(sales)
    1
    >>> sale = sales[0]
    >>> len(sale.lines)
    1
    >>> line = sale.lines[0]
    >>> line.product.id
    1
    >>> line.quantity
    10.0

Add the same item again to the cart, it will create a new cart/sale::

     >>> with app.test_client() as c:
     ...     c.post('/cart/add', data={
     ...         'product': product.id,
     ...         'quantity': 20,
     ...     })
     <Response streamed [302 FOUND]>

Check if the Sale Order is created::

    >>> sales = Sale.find([])
    >>> len(sales)
    2
    >>> sale = sales[0]
    >>> len(sale.lines)
    1
    >>> line = sale.lines[0]
    >>> line.product.id
    1
    >>> line.quantity
    20.0

Create a new product::

    >>> product2 = Product()
    >>> product2.name = 'product 2'
    >>> product2.category = category
    >>> product2.default_uom = unit
    >>> product2.type = 'stockable'
    >>> product2.purchasable = True
    >>> product2.salable = True
    >>> product2.list_price = Decimal('10')
    >>> product2.cost_price = Decimal('5')
    >>> product2.account_expense = expense
    >>> product2.account_revenue = revenue
    >>> product2.account_journal_stock_input = stock_journal
    >>> product2.account_journal_stock_output = stock_journal
    >>> product2.save()

Add both products to the cart and verify::

    >>> with app.test_client() as c:
    ...     c.post('/cart/add', data={
    ...         'product': product.id,
    ...         'quantity': 5,
    ...     })
    ...     c.post('/cart/add', data={
    ...         'product': product2.id,
    ...         'quantity': 15,
    ...     })
    <Response streamed [302 FOUND]>
    <Response streamed [302 FOUND]>

    >>> sales = Sale.find([])
    >>> len(sales)
    3
    >>> sale = sales[0]
    >>> len(sale.lines)
    2
    >>> line1 = sale.lines[0]
    >>> line1.product.id
    1
    >>> line1.quantity
    5.0
    >>> line2 = sale.lines[1]
    >>> line2.product.id
    2
    >>> line2.quantity
    15.0

Add both products to the cart, then delete a line, then clear cart and verify all::

    >>> with app.test_client() as c:
    ...     c.post('/cart/add', data={
    ...         'product': product.id,
    ...         'quantity': 10,
    ...     })
    ...     c.post('/cart/add', data={
    ...         'product': product2.id,
    ...         'quantity': 15,
    ...     })
    ...     sales = Sale.find([])
    ...     len(sales)
    ...     sale = sales[0]
    ...     len(sale.lines)
    ...     line1 = sale.lines[0]
    ...     line1.product.id
    ...     line1.quantity
    ...     line2 = sale.lines[1]
    ...     line2.product.id
    ...     line2.quantity
    ...     c.get('/cart/delete/' + str(line1.id))
    ...     sales = Sale.find([])
    ...     len(sales)
    ...     sale = sales[0]
    ...     len(sale.lines)
    ...     line = sale.lines[0]
    ...     line.product.id
    ...     line.quantity
    ...     c.get('/cart/clear')
    ...     sales = Sale.find([])
    ...     len(sales)
    ...     sale = sales[0]
    <Response streamed [302 FOUND]>
    <Response streamed [302 FOUND]>
    4
    2
    1
    10.0
    2
    15.0
    <Response streamed [302 FOUND]>
    4
    1
    2
    15.0
    <Response streamed [302 FOUND]>
    3

Test cart with login::

Call the response of /cart and check if it retains same cart::

    >>> with app.test_client() as client:
    ...     client.post('/login', 
    ...         data=dict(email='user@example.com', password='password'))
    ...     cart_response = client.get('/cart')
    ...     cart_response_2 = client.get('/cart')
    ...
    <Response streamed [302 FOUND]>
    >>> cart_response.data == cart_response_2.data
    True

Add items to a cart::
    >>> with app.test_client() as client:
    ...     client.post('/login', 
    ...         data=dict(email='user@example.com', password='password'))
    ...     cart_response = client.get('/cart')
    ...     client.post('/cart/add', data={
    ...         'product': product.id,
    ...         'quantity': 10,
    ...     })
    ...
    <Response streamed [302 FOUND]>
    <Response streamed [302 FOUND]>

Check if the Sale Order is created::

    >>> sales = Sale.find([])
    >>> len(sales)
    4
    >>> sale = sales[0]
    >>> len(sale.lines)
    1
    >>> line = sale.lines[0]
    >>> line.product.id
    1
    >>> line.quantity
    10.0

Add the same item but 20 units::

    >>> with app.test_client() as client:
    ...     rv1 = client.post('/login', 
    ...         data=dict(email='user@example.com', password='password'))
    ...     cart_response = client.get('/cart')
    ...     rv2 = client.post('/cart/add', data={
    ...         'product': product.id,
    ...         'quantity': 20,
    ...     })
    >>> rv1.status_code == 302
    True
    >>> rv2.status_code == 302
    True
    >>> sales = Sale.find([])
    >>> len(sales)
    4
    >>> sale = sales[0]
    >>> sale.total_amount == Decimal('200')
    True
    >>> len(sale.lines)
    1
    >>> line = sale.lines[0]
    >>> line.product.id
    1
    >>> line.quantity
    20.0

Now add 5 units of this product to the cart::

    >>> with app.test_client() as client:
    ...     client.post('/login', 
    ...         data=dict(email='user@example.com', password='password'))
    ...     cart_response = client.get('/cart')
    ...     client.post('/cart/add', data={
    ...         'product': product2.id,
    ...         'quantity': 5,
    ...     })
    <Response streamed [302 FOUND]>
    <Response streamed [302 FOUND]>
    >>> Sale = Model.get('sale.sale')
    >>> sales = Sale.find([])
    >>> len(sales)
    4
    >>> sale = sales[0]
    >>> sale.total_amount == Decimal('250')
    True
    >>> len(sale.lines)
    2
    >>> line = sale.lines[0]
    >>> line.product.id
    1
    >>> line.quantity
    20.0
    >>> line2 = sale.lines[1]
    >>> line2.product.id == product2.id
    True
    >>> line2.quantity
    5.0

Delete a line in the cart::

    >>> with app.test_client() as client:
    ...     client.post('/login', 
    ...         data=dict(email='user@example.com', password='password'))
    ...     cart_response = client.get('/cart')
    ...     client.get('/cart/delete/' + str(line.id))
    <Response streamed [302 FOUND]>
    <Response streamed [302 FOUND]>
    >>> Sale = Model.get('sale.sale')
    >>> sales = Sale.find([])
    >>> len(sales)
    4
    >>> sale = sales[0]
    >>> sale.total_amount == Decimal('50')
    True
    >>> len(sale.lines)
    1
    >>> line = sale.lines[0]
    >>> line.id == line2.id
    True

Test Clearing of cart::

    >>> with app.test_client() as client:
    ...     client.post('/login', 
    ...         data=dict(email='user@example.com', password='password'))
    ...     cart_response = client.get('/cart')
    ...     client.get('/cart/clear')
    <Response streamed [302 FOUND]>
    <Response streamed [302 FOUND]>
    >>> Sale = Model.get('sale.sale')
    >>> sales = Sale.find([])
    >>> len(sales)
    3

Create another party::

    >>> customer2 = Party(name='Customer2', company=company)
    >>> customer2.save() 
    >>> email2 = ContactMechanism(type='email', value='user@example2.com', 
    ...     party=customer2)
    >>> email2.save()
    >>> customer2.addresses.append(Address(
    ...     name='Customer Address', email=email2, password='password'))
    >>> customer2.save()

Now try to fetch cart for both the customers::

    >>> with app.test_client() as client:
    ...     client.post('/login', 
    ...         data=dict(email='user@example.com', password='password'))
    ...     client.get('/cart')
    <Response streamed [302 FOUND]>
    <Response streamed [200 OK]>
    >>> with app.test_client() as client:
    ...     client.post('/login', 
    ...         data=dict(email='user@example2.com', password='password'))
    ...     client.get('/cart')
    <Response streamed [302 FOUND]>
    <Response streamed [200 OK]>
    >>> Sale = Model.get('sale.sale')
    >>> sales = Sale.find([])
    >>> len(sales)
    3
