use library_system;

drop table if exists Book2;
drop table if exists Book1;
drop table if exists Book_Author;
drop table if exists Hold;
drop table if exists Copy;
drop table if exists Book;
drop table if exists Publisher;
drop table if exists AuthorTemp;
drop table if exists Author;
drop table if exists Patron;

drop procedure if exists populateCopy;



CREATE TABLE IF NOT EXISTS Book1(
    id INT,
    title TEXT,
    authors TEXT,
    isbn10 VARCHAR(15),
    isbn13 BIGINT,
    lang VARCHAR(10),
    page_count INT,
    pub_date TEXT,
    publisher TEXT,
    primary key (id)
);

CREATE TABLE IF NOT EXISTS Book2(
    isbn13 BIGINT,
    subtitle TEXT,
    categories TEXT,
    cover_image TEXT,
    summary LONGTEXT,
    page_count TEXT,
    primary key (isbn13)
);

CREATE TABLE if not EXISTS Publisher(
pub_id INT not null auto_increment,
pub_name TEXT,
primary key(pub_id)
);

CREATE TABLE if not EXISTS AuthorTemp(
temp_id BIGINT not null auto_increment,
temp_name TEXT,
primary key(temp_id)
);


CREATE TABLE if not EXISTS Author(
author_name TEXT
);

create table if not exists Patron(
    id int(10) not null auto_increment,
    username varchar(50) not null,
    password varchar(128) not null,
    email varchar(128) not null,
    first_name varchar(128) not null,
    last_name varchar(128) not null,
    primary key(id)
);

/* Load data from the 2 excel sheets into Book1 and Book2 Tables */
LOAD DATA INFILE '/var/lib/mysql-files/books1.csv' 
INTO TABLE Book1
FIELDS TERMINATED BY ',' LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(id, title, authors, @dummy, isbn10, isbn13, lang, page_count, @dummy, @dummy, @d, publisher, @dummy)
SET pub_date = STR_TO_DATE(@d, '%m/%d/%Y');


LOAD DATA INFILE '/var/lib/mysql-files/books2.csv' 
INTO TABLE Book2
FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(isbn13, @dummy, @dummy, subtitle, @dummy, categories, cover_image, summary, @dummy, @dummy, page_count, @dummy);

/* Join Book1 and Book2 together to create a single Book entity with all the information */
CREATE TABLE Book AS
SELECT title, authors, isbn10, Book2.isbn13, lang, Book2.page_count, pub_date, publisher, subtitle, categories, cover_image, summary
FROM Book1 inner join Book2 
using (isbn13);
ALTER TABLE Book ADD primary key(isbn13);
ALTER TABLE Book order by isbn13;

/* Create publisher table */
INSERT INTO Publisher (pub_name)
SELECT DISTINCT publisher 
FROM Book
order by publisher;

/* Used for operations to split Authors into different lines. Some books have multiple authors */
INSERT INTO AuthorTemp (temp_name)
SELECT DISTINCT authors
FROM Book;

/*
Load data into Author table
Code From: https://www.databasestar.com/sql-split-string/#MySQL
*/
INSERT INTO Author
SELECT DISTINCT
SUBSTRING_INDEX(
  SUBSTRING_INDEX(
    temp_name, '/', numbers.n
  ), '/', -1
) AS category_name
FROM
  (SELECT 1 AS n UNION ALL
   SELECT 2 UNION ALL SELECT 3 UNION ALL
   SELECT 4 UNION ALL SELECT 5
   ) numbers
INNER JOIN AuthorTemp
  ON CHAR_LENGTH(temp_name)
     - CHAR_LENGTH(REPLACE(temp_name, '/', '')) >= numbers.n-1;

ALTER TABLE Author order by author_name;
ALTER TABLE Author ADD author_id INT NOT NULL auto_increment primary key;

/*
Seperate multiple authors into seperate entries
Code From: https://www.databasestar.com/sql-split-string/#MySQL
*/
CREATE TABLE Book_Author AS
SELECT
isbn13,
SUBSTRING_INDEX(
  SUBSTRING_INDEX(
    authors, '/', numbers.n
  ), '/', -1
) AS author
FROM
  (SELECT 1 AS n UNION ALL
   SELECT 2 UNION ALL SELECT 3 UNION ALL
   SELECT 4 UNION ALL SELECT 5
   ) numbers
INNER JOIN Book
  ON CHAR_LENGTH(authors)
     - CHAR_LENGTH(REPLACE(authors, '/', '')) >= numbers.n-1
ORDER BY isbn13, n;

ALTER TABLE Book_Author ADD author_id INT not null;
UPDATE Book_Author
inner join Author 
on Book_Author.author = Author.author_name
SET Book_Author.author_id = Author.author_id;

ALTER TABLE Book_Author drop author;
ALTER TABLE Book_Author ADD constraint fk_author_id FOREIGN KEY (author_id) REFERENCES Author(author_id);
ALTER TABLE Book_Author ADD constraint fk_isbn13 FOREIGN KEY (isbn13) REFERENCES Book(isbn13);


/* update Book table to include Publisher ID instead of publisher name*/ 
ALTER TABLE Book ADD publisher_id INT not null;
UPDATE Book
inner join Publisher
on Book.publisher = Publisher.pub_name
SET Book.publisher_id = Publisher.pub_id;
ALTER TABLE Book ADD constraint fk_pub_id FOREIGN KEY (publisher_id) REFERENCES Publisher(pub_id);
ALTER TABLE Book DROP publisher;

ALTER TABLE Book DROP authors;

/* Drop all the temporary tables */
DROP TABLE AuthorTemp;
DROP TABLE Book1;
DROP TABLE Book2;

create table if not exists Copy(
id int not null primary key auto_increment,
isbn13 bigint not null,
available varchar(12),
foreign key (isbn13) references Book(isbn13)
);

/* Each Book can have 1-3 copies that the library owns
randomly assign the number of copies each book has */
create procedure populateCopy()
begin
    declare i int default 0;
    declare j int default 0;
    declare total int;
    declare numCopies int default 0;
    set total = (select count(*) from Book);
    while i < total do
        set j = 0;
        set numCopies = (select floor(rand() * 3) + 1);
        while j < numCopies do
            insert into Copy (isbn13, available) values ((select isbn13 from Book limit i, 1), "Available");
            set j = j + 1;
        end while;
        set i = i + 1;
    end while;
end;

call populateCopy;

create table if not exists Hold(
id int primary key auto_increment,
copy_id int,
patron_id int,
hold_date date,
foreign key (patron_id) references Patron(id),
foreign key(copy_id) references Copy(id)
);