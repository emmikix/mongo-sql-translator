import re

# maps mongo operator format to SQL format
OperatorDict = {
    '"$and"': "AND",
    '"$or"': "OR",
    '"$in"': "IN",
    '"$lt"': "<",
    '"$lte"': "<=",
    '"$gt"': ">",
    '"$gte"': ">=",
    '"$ne"': "!="
}

# tokenizes the MongoDB query for parsing
def Lexer(mongo_str):
    tokens = []
    chars_keep = {"{","[","}","]",","}
    regex_fields = r'([\'"$\w.])'

    i = 0
    while i < len(mongo_str):
        if mongo_str[i] in chars_keep:
            tokens.append(mongo_str[i])
            i += 1
        elif re.search(regex_fields, mongo_str[i]):
            start_index = i
            while i < len(mongo_str) and re.search(regex_fields, mongo_str[i]):
                i += 1
            else:
                if i < len(mongo_str):
                    tokens.append(mongo_str[start_index:i])
            if mongo_str[start_index:i] == '"$in"':
                set_start = i
                while mongo_str[i] != "[":
                    i += 1
                else:
                    set_start = i
                    while mongo_str[i] != "]":
                        i += 1
                    else:
                        tokens.append(mongo_str[set_start:i+1])
                        i += 1
        else:
            i += 1
    return tokens

# iterates through tokens to add them to a dictionary before formatting to SQL
# parameters: tokens is list of tokens, add_brackets is a boolean for whether
# the statement is within a nested and/or list
def LoadTokens(tokens,add_brackets):
    token_dict = {}
    brackets = []
    field_ready = False
    cur_key = None
    and_or_list = []
    i = 0
    # iterates through tokens looking for keys, values(fields), and
    # nested brackets to call inside of recursively
    while i < len(tokens):
        # captures key (lhs)
        if tokens[i].startswith("\"") and field_ready == False:
                    token_dict[tokens[i]] = None
                    field_ready = True
                    cur_key  = tokens[i]
        elif (tokens[i] == "[" or tokens[i] == "{") and field_ready == True:
            brackets.append(tokens[i])
            start_index = i
            i += 1
            while i < len(tokens) and len(brackets) > 0:
                if tokens[i] == "[" or tokens[i] == "{":
                    brackets.append(tokens[i])
                if tokens[i] == "]" or tokens[i] == "}":
                    brackets = brackets[1:]
                i += 1
            else:
                if i < len(tokens):
                    new_stmt = tokens[start_index:i]
                    in_brackets = True if new_stmt[0] == ("[") else False
                    # recursively call in new statement inside of brackets
                    dict_to_load = LoadTokens(new_stmt,in_brackets)
                    # continue to add it inside dictionary or and/or list
                    # depending if the current key is $and or $or or neither
                    if add_brackets == True and not cur_key.startswith("$"):
                        if tokens[i] == ",":
                            token_dict[cur_key] = dict_to_load
                        else:
                            token_dict[cur_key] = dict_to_load
                            and_or_list.append(token_dict.copy())
                            token_dict.clear()
                    elif add_brackets == True and cur_key.startswith("$"):
                        and_or_list.append({cur_key:dict_to_load})
                    else:
                        token_dict[cur_key] = dict_to_load
                    field_ready = False
                    cur_key  = None
        # captures terminal fields to match the current key
        elif field_ready == True and len(brackets) == 0:
            regex_fields = r'([\'"\w])'
            if re.search(regex_fields, tokens[i][0]) or tokens[i].startswith("["): # for $in :
                token_dict[cur_key] = tokens[i]
                field_ready = False
            if add_brackets == True and not cur_key.startswith("$") and tokens[i+1] != ",":
                token_dict[cur_key] = tokens[i]
                and_or_list.append(token_dict.copy())
                token_dict.clear()
        i += 1
    if add_brackets == True:
        return and_or_list
    else:
        return token_dict
# query_a = '{"$or": [{"status": "A","size.uom": "cm"},{"instock.qty": {"$gt": true}}]}'
# query_b = '{"status": "A", "qty": {"$lt": 30}}'
# query_c = '{"$and": [{"status": "A"}, {"qty": {"$ne": 30},{"status": "A"}}]}'
# query_d = '{"status": "A","$or": [{"instock.qty": {"$gt": 50}},{"instock.warehouse": {"$in": ["B"]}, "size.uom": "cm"}]}'
# mongo_tokens = Lexer(query_d)
# LoadTokens(mongo_tokens, False)

# data structure for expression tokens
class Expression:
    def __init__(self):
        self.name = None
        self.operator = None
        self.operand = None

    # for pretty printing
    def __repr__(self):
        return "\n% s % s % s\n" % (self.name, self.operator, self.operand)

# data structure for "SELECT", "FROM", and "WHERE" clauses of a SQL query
class SQLStatement:
    # initialize SQLStatement object with instance variables to represent
    # "SELECT", "FROM", and "WHERE" clauses
    def __init__(self):
        self.sql_from = None
        self.sql_select = "*"
        self.sql_where = ""

    # for pretty printing
    def __repr__(self):
        return "sql_select:% s \nsql_from:% s \nsql_where:% s" % (self.sql_select, self.sql_from, self.sql_where)

    # format instance variables to a SQL query string
    def ToSQLStr(self):
        if self.sql_where != "":
            return("SELECT " + self.sql_select + " FROM " + self.sql_from + " WHERE " + self.sql_where + ";")
        else:
            return("SELECT " + self.sql_select + " FROM " + self.sql_from + ";")

    # helper for FormatWhereClause that recursively descends into
    # evaluating the expression in a dict or a list of dict expressions
    def FormatOperand(self,operand):
        if type(operand) == dict:
            for key, value in operand.items():
                if type(value) == str:
                    if value[0] == '"' and not value[1:-1].isdigit():
                        temp_operand = "\'" + value[1:-1] + "\'"
                    elif value[0] == '"' and value[1:-1].isdigit():
                        temp_operand = value[1:-1]
                    elif value[0] == "[":
                        result = re.sub(r'(\"(.*)\")',r"'\2'",value)
                        temp_operand = "(" + result[1:-1] + ")"
                    else:
                        temp_operand = value
                else:
                    temp_operand = str(value)
                return OperatorDict[key], temp_operand
        elif type(operand) == list:
            return [self.FormatWhereClause(x) for x in operand]

    # format "WHERE" clause from mongo to SQL
    def FormatWhereClause(self,where):
        temp = Expression()
        temp_list = []

        # iterate through json dict of the "WHERE" clause to extract
        # components of the expressions it contains and then recombine them
        for key,value in where.items():

            temp.name = key[1:-1]

            if type(value) == str:
                temp.operator = "="
                if value[0] == '"':
                    temp.operand = "\'" + value[1:-1] + "\'"
                else:
                    temp.operand = value.upper()
                temp_list.append(temp.name + " " + temp.operator + " " + temp.operand)
            elif type(value) == dict:
                temp.operator, temp.operand = self.FormatOperand(value)
                temp_list.append(temp.name + " " + temp.operator + " " + temp.operand)
            elif type(value) == list:
                temp_str = ""
                if key == '"$or"':
                    temp_str = "(" + " OR ".join(self.FormatOperand(value)) + ")"
                elif key == '"$and"':
                    temp_str = "(" + " AND ".join(self.FormatOperand(value)) + ")"
                if(temp_str):
                    temp_list.append(temp_str)

        # take care of comma separated mongo "AND" expressions converting
        # them to SQL format
        and_str = ""
        if len(temp_list) > 1:
            and_str = "(" + " AND ".join(temp_list) + ")"
        else:
            try:
                and_str = temp_list[0]
            except:
                print("temp_list of where expressions is empty")
        return and_str

    # takes a MongoDB query and extracts SQL "FROM", "SELECT", and
    # "WHERE" clauses.
    # assumes valid input with regular naming conventions for databases
    # and fields
    def GetSQL(self, test_str):
        # initial simple test for correct formatting of Mongo query
        regex = r'(^db.)([\w]+)(\.find)\((.*)\)'
        query = re.search(regex, test_str)

        if not query:
            return "format of this query is incorrect"

        # extract SQL "FROM" clause
        self.sql_from = query.group(2)

        # extract SQL "SELECT" and SQL "WHERE" clauses from original Mongo query
        regex = r'({.*}),\s?({(?:[\w.\s"]*:\s?\d*,?)*})'
        select_where = re.search(regex,query.group(4))

        # extract SQL "SELECT" clause.
        # if query did not match as having both "SELECT" and "WHERE" statements,
        # just capture "WHERE" (even if it doesn't exist).
        # else if there is a projection, extract values for SQL "SELECT" clause
        if not select_where:
            regex = r'({.*})'
            select_where = re.search(regex,query.group(4))
        else:
            # put all projections (field name and value) into a list with findall
            regex = r'"?[\w.]+"?:\s?\d'
            projections = re.findall(regex,select_where.group(2))

            # iterate through projections list, extracting the name of the field
            # and value with regex groups. if its value is 1, it is projected
            # and added to the SQL "SELECT" clause. projections of 0 are not
            # addressed because all of the table fields are unknown.
            regex = r'"?([\w.]+)"?:\s?(\d)'
            temp_select_list = []
            for p in projections:
                p_regex = re.search(regex,p)
                if p_regex.group(2) == "1":
                    temp_select_list.append(p_regex.group(1))
            self.sql_select = ", ".join(temp_select_list)

        # extract SQL "WHERE" clause by converting mongo query to a json dict
        # and using recursive descent to translate its expressions to SQL
        if select_where.group(1) != '{}':
            # add or alter quotes for json formatting
            result = re.sub(r'(\$?[\w.]+):',r'"\1":',select_where.group(1))
            result = re.sub(r'(\'(.*)\')',r'"\2"',result)

            # convert formatted "WHERE" clause into a json dict
            try:
                # where = json.loads(result)
                where_tokens = Lexer(result)
                where = LoadTokens(where_tokens, False)
            except:
                return "\"WHERE\" clause could not be loaded to json"
            self.sql_where = self.FormatWhereClause(where)
            if self.sql_where.startswith("(") and self.sql_where.endswith(")"):
                self.sql_where = self.sql_where[1:-1]

        # finally, return formatted SQL query
        return self.ToSQLStr()
