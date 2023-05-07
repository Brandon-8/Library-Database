from flask import Flask, render_template, request, flash, redirect, session, url_for
from flaskext.mysql import MySQL
import re
from passlib.hash import sha256_crypt

app = Flask(__name__)
app.config['SECRET_KEY'] = '1ddzRohZ10uag5pIATG1'
library = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'my-secret-pw'
app.config['MYSQL_DATABASE_DB'] = 'library_system'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
library.init_app(app)


@app.route('/')
def index():
    session['loggedin'] = False
    return render_template('home.html', loginVal=session['loggedin'], activePage="info")

# Home page
@app.route('/home')
def home():
    return render_template('home.html', loginVal=session['loggedin'], activePage="info")

# search page
@app.route('/search', methods=('GET', 'POST'))
@app.route('/search/<author>', methods=('GET', 'POST'))
def search(author=None):
    titles = 0
    authors = 0  
    conn = library.connect() 
    cursor = conn.cursor() 
    # search on author
    if author and author != 'search':
        cursor.execute("drop view if exists temp1, temp2;")
        cursor.execute("create view temp1 (isbn13, author_name, author_id) as "
                        "SELECT isbn13, author_name, Author.author_id FROM Book_Author inner join Author "
                        "on Author.author_id = Book_Author.author_id "
                        "where Author.author_id = %s;", (author,))
            
        cursor.execute("create view temp2 (isbn13, author_name, author_id) as "
                        "Select isbn13, author_name, Author.author_id from Book_Author inner join Author "
                        "on Author.author_id = Book_Author.author_id "
                        "where Book_Author.isbn13 in (Select isbn13 from temp1);")
                
        cursor.execute("select * from temp2")
        authors = cursor.fetchall()

        cursor.execute("select * from Book where Book.isbn13 in (select isbn13 from temp2) order by isbn13;")
        titles = cursor.fetchall()
        cursor.execute("drop view if exists temp1, temp2;")       
    
    elif request.method == 'POST':
        query = request.form['query']
        field = request.form['field']
        # Search by ISBN13
        if field == 'isbn' and len(query) == 13: #isbn13
            cursor.execute("SELECT * FROM Book where isbn13=%s;", (query,))
            titles = cursor.fetchall()
            if titles:
                cursor.execute("SELECT isbn13, author_name, Author.author_id FROM Author inner join Book_Author " 
                                "on Author.author_id = Book_Author.author_id "
                                "where Book_Author.isbn13=%s;", (query,))
                authors = cursor.fetchall()
            else:
                authors = 0

        elif field == 'isbn': #isbn 10
            cursor.execute("SELECT * FROM Book where isbn10=%s", (query,))
            titles = cursor.fetchall()
            if titles:
                cursor.execute("SELECT Book.isbn13, author_name, a.author_id  FROM Book inner join "
                                "(select isbn13, Author.author_id, author_name from Author inner join Book_Author "
                                "on Author.author_id = Book_Author.author_id) a "
                                "on Book.isbn13 = a.isbn13 where Book.isbn10=%s;", (query,))
                authors = cursor.fetchall()
            else:
                authors = 0
        # search by title
        elif field == 'title':
            cursor.execute("select * from Book where Book.title like %s;", ('%' + query + '%'))
            titles = cursor.fetchall()
            cursor.execute("SELECT isbn13, author_name, Author.author_id "
                           "FROM Author inner join Book_Author on Author.author_id = Book_Author.author_id "
                            "where Book_Author.isbn13= any (select isbn13 from Book where Book.title like %s);", ('%' + query + '%'))
            authors = cursor.fetchall()
        
        # search by author
        elif field == 'author':
            cursor.execute("drop view if exists temp1, temp2;")
            cursor.execute("create view temp1 (isbn13, author_name, author_id) as "
                            "SELECT isbn13, author_name, Author.author_id FROM Book_Author inner join Author "
                            "on Author.author_id = Book_Author.author_id "
                            "where Author.author_id = any (SELECT author_id FROM Author where author_name like %s);", ('%' + query + '%',))
            
            cursor.execute("create view temp2 (isbn13, author_name, author_id) as "
                            "Select isbn13, author_name, Author.author_id from Book_Author inner join Author "
                            "on Author.author_id = Book_Author.author_id "
                            "where Book_Author.isbn13 in (Select isbn13 from temp1);")
                

            cursor.execute("select * from temp2")
            authors = cursor.fetchall()

            cursor.execute("select * from Book where Book.isbn13 in (select isbn13 from temp2) order by Book.isbn13;")
            titles = cursor.fetchall()
            cursor.execute("drop view if exists temp1, temp2;")

    conn.close()
    return render_template('search.html', loginVal=session['loggedin'], activePage="search", titles=titles, authors=authors)

# Display full page view of Book
@app.route('/book/<title>', methods=('GET', 'POST'))
def book(title):
    conn = library.connect()
    cursor = conn.cursor()
    # Handles Place Hold request
    if request.method == 'POST':
        if session['loggedin']:
            # check if user already placed a hold on this book
            cursor.execute("select Hold.id from Hold inner join Copy on Copy.id=Hold.copy_id "
                            "where patron_id=%s and Copy.isbn13=%s;", (session['id'], title))
            if cursor.fetchone():
                flash("You already placed a hold on this book")
            else:
                cursor.execute("select current_date();")
                date = cursor.fetchone()
                cursor.execute("select id from Copy where isbn13=%s and available='Available'", (title,))
                copies = cursor.fetchone()
                if copies: # a copy is currently available
                    cursor.execute("insert into Hold (copy_id, hold_date, patron_id) " 
                                    "values (%s, %s, %s);", (copies, date, session['id']))
                    cursor.execute("update Copy set available='On Hold' where id=%s;", (copies,))
                    conn.commit()
                    flash("Hold successfully Placed")
                else: # no copies currently available
                    flash("Cannot place a hold request")
        else:
            flash("Please log in to place a hold request")
    # Get Book and Author info
    cursor.execute("SELECT title, isbn10, isbn13, lang, page_count, pub_date, subtitle, categories, cover_image, summary, pub_name "
                    "FROM Book inner join Publisher "
                    "on Book.publisher_id = Publisher.pub_id where Book.isbn13=%s;", (title,))
    info = cursor.fetchone()
    cursor.execute("SELECT author_name, Author.author_id FROM Author inner join Book_Author " 
                    "on Author.author_id = Book_Author.author_id "
                    "where Book_Author.isbn13=%s;", (title,))
    authors = cursor.fetchall()
    # get num of available copies
    cursor.execute("select available from Copy where isbn13=%s", (title,))
    copies = cursor.fetchall()
    available = 0
    for copy in copies:
        if copy[0] == 'Available':
            available += 1
    ret = str(available) + ' (of ' + str(len(copies)) + ')'
    conn.close()
    return render_template('book.html', loginVal=session['loggedin'], activePage="search", title=info, authors=authors, copies=ret)

# get search results by clicking on author link
@app.route('/author/<author>')
def author(author):
    conn = library.connect()
    cursor = conn.cursor()
    cursor.execute("drop view if exists temp1, temp2;")
    cursor.execute("create view temp1 (isbn13, author_name, author_id) as "
                    "SELECT isbn13, author_name, Author.author_id FROM Book_Author inner join Author "
                    "on Author.author_id = Book_Author.author_id "
                    "where Author.author_id = %s;", (author,))
        
    cursor.execute("create view temp2 (isbn13, author_name, author_id) as "
                    "Select isbn13, author_name, Author.author_id from Book_Author inner join Author "
                    "on Author.author_id = Book_Author.author_id "
                    "where Book_Author.isbn13 in (Select isbn13 from temp1);")
            
    cursor.execute("select * from temp2")
    authors = cursor.fetchall()

    cursor.execute("select * from Book where Book.isbn13 in (select isbn13 from temp2);")
    titles = cursor.fetchall()
    cursor.execute("drop view if exists temp1, temp2;")
    conn.close()
    return render_template('search.html', loginVal=session['loggedin'], activePage="search", titles=titles, authors=authors)

# login / sign up
@app.route('/login', methods=('GET', 'POST'))
def login():
    # log out the current user
    if session['loggedin']:
        session['loggedin'] = False
        session.pop('id', None)
        session.pop('username', None)
        flash("You have successfully logged out")
        return render_template('login.html', loginVal=False, activePage="login")
    
    if request.method == 'POST':
        username = request.form['username']
        usernameNew = request.form['usernameNew']
        password = request.form['password']
        passwordNew = request.form['passwordNew']
        emailNew = request.form['emailNew']
        fName = request.form['fName']
        lName = request.form['lName']
        
        conn = library.connect()
        cursor = conn.cursor()

        # sign up new user
        if 'Sign Up' in request.form:
            if not usernameNew:
                flash("Please provide a username")
            elif not passwordNew:
                flash("Please provide a password")
            elif not emailNew:
                flash("Please provide an email")
            elif not fName:
                flash("Please provide a first name")
            elif not lName:
                flash("Please provide a last name")
            else:
                cursor.execute("select username from Patron where username=%s;", (usernameNew,))
                if cursor.fetchone():
                    flash("Username already taken")
                else:
                    # info about sessions and regrex from https://www.geeksforgeeks.org/how-to-use-flask-session-in-python-flask/
                    # check email
                    if re.match(r'[^@]+@[^@]+\.[^@]+', emailNew):
                        cursor.execute("select email from Patron where email=%s;", (emailNew,))
                        if cursor.fetchone():
                            flash("An account with this email already exists")
                        else: # add new user to the system
                            passwordHash = sha256_crypt.hash((str(passwordNew))) # hash password
                            cursor.execute("insert into Patron (username, password, email, first_name, last_name) "
                                        "values (%s, %s, %s, %s, %s);", (usernameNew, passwordHash, emailNew, fName, lName))
                            conn.commit()
                            # create session data
                            cursor.execute("select id, username, email, first_name, last_name from Patron where username=%s;", (usernameNew,))
                            account = cursor.fetchone()
                            session['loggedin'] = True
                            session['id'] = account[0]
                            session['username'] = account[1]
                            info = [session['id'], session['username'], account[2], account[3], account[4]]
                            conn.close()
                            flash("New Account Created")
                            return redirect(url_for('account', loginVal=session['loggedin'], activePage="account", user=info))                    
                    else:
                        flash("Invalid Email")

        # log in existing user
        elif 'Log In' in request.form:
            if not username:
                flash("Please provide a username or email")
            elif not password:
                flash("Please provide a password")
            elif '@' in username: # user gave email
                cursor.execute("select id, username, password, email, first_name, last_name from Patron where email=%s;", (username,))
                account = cursor.fetchone()
                if not account:
                    flash("There is no account with that email")
                else:                  
                    if sha256_crypt.verify(str(password), account[2]):
                        # create session data
                        session['loggedin'] = True
                        session['id'] = account[0]
                        session['username'] = account[1]
                        info = [session['id'], session['username'], account[3], account[4], account[5]]
                        conn.close()
                        return redirect(url_for('account', loginVal=session['loggedin'], activePage="account", user=info)) 
                    else:
                        flash("Invalid password")
            else: # user gave username
                cursor.execute("select id, username, password, email, first_name, last_name from Patron where username=%s", (username,))
                account = cursor.fetchone()
                if not account:
                    flash("There is no account with that username")
                else:
                    if sha256_crypt.verify(str(password), account[2]):
                        # create session data
                        session['loggedin'] = True
                        session['id'] = account[0]
                        session['username'] = account[1]
                        info = [session['id'], session['username'], account[3], account[4], account[5]]
                        conn.close()
                        return redirect(url_for('account', loginVal=session['loggedin'], activePage="account", user=info))                    
                    else:
                        flash("Invalid password")
        conn.close()
    return render_template('login.html', loginVal=False, activePage="login")

# get account info of current user
@app.route('/account', methods=('GET', 'POST'))
def account():
    conn = library.connect()
    cursor = conn.cursor()
    # user cancels a hold
    if request.method == 'POST':
        isbn = request.form.get("book", "")
        cursor.execute("set @temp = (select Hold.copy_id from Hold inner join Copy on Hold.copy_id=Copy.id "
                        "where Copy.isbn13=%s and Hold.patron_id=%s);", (isbn, session['id']))
        cursor.execute("update Copy set available='Available' where Copy.id = @temp;")
        cursor.execute("delete from Hold where Hold.copy_id=@temp and Hold.patron_id=%s;", (session['id'],))
        conn.commit()
        flash("Hold successfully canceled")
    cursor.execute("select email, first_Name, last_Name from Patron where id=%s;", (session['id']))
    data = cursor.fetchone()
    info = [session['id'], session['username'], data[0], data[1], data[2]]
    cursor.execute("select * from Hold where patron_id=%s", session['id'])
    holds = cursor.fetchall()

    cursor.execute("select * from Book where Book.isbn13 = "
                    "any (select isbn13 from Hold inner join Copy on Hold.copy_id=Copy.id "
                    "where Hold.patron_id=%s);", (session['id']))
    titles = cursor.fetchall()

    cursor.execute("select isbn13, author_name, Author.author_id from Author inner join Book_Author "
                    "on Author.author_id = Book_Author.author_id where Book_Author.isbn13= "
                    "any (select isbn13 from Hold inner join Copy on Hold.copy_id=Copy.id "
                    "where Hold.patron_id=%s);", (session['id']))
    authors=cursor.fetchall()
    conn.close()
    return render_template('account.html', loginVal=session['loggedin'], activePage="account", user=info, holds=holds, titles=titles, authors=authors)

# forgot password page, feature not implemented
@app.route('/forgotPassword', methods=('GET', 'POST'))
def resetPassword():
    if request.method == 'POST':
        if 'submit' in request.form:
            flash("This feature is not implemented")
        else:
            return redirect(url_for('login'))
    return render_template('forgotPassword.html', loginVal=session['loggedin'])

if __name__ == '__main__':
    app.run(debug=True)